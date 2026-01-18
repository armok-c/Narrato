#!/usr/bin/env python
# -*- coding: UTF-8 -*-

'''
@Project: NarratoAI
@File   : generate_video
@Author : Viccy同学
@Date   : 2025/5/7 上午11:55 
'''

import os
import traceback
import tempfile
from typing import Optional, Dict, Any
from loguru import logger
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    afx
)
from moviepy.video.tools.subtitles import SubtitlesClip
from PIL import ImageFont

from app.utils import utils
from app.models.schema import AudioVolumeDefaults
from app.services.audio_normalizer import AudioNormalizer, normalize_audio_for_mixing


def is_valid_subtitle_file(subtitle_path: str) -> bool:
    """
    检查字幕文件是否有效

    参数:
        subtitle_path: 字幕文件路径

    返回:
        bool: 如果字幕文件存在且包含有效内容则返回True，否则返回False
    """
    if not subtitle_path or not os.path.exists(subtitle_path):
        return False

    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # 检查文件是否为空
        if not content:
            return False

        # 检查是否包含时间戳格式（SRT格式的基本特征）
        # SRT格式应该包含类似 "00:00:00,000 --> 00:00:00,000" 的时间戳
        import re
        time_pattern = r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}'
        if not re.search(time_pattern, content):
            return False

        return True
    except Exception as e:
        logger.warning(f"检查字幕文件时出错: {str(e)}")
        return False


def merge_materials(
    video_path: str,
    audio_path: str,
    output_path: str,
    subtitle_path: Optional[str] = None,
    bgm_path: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    合并视频、音频、BGM和字幕素材生成最终视频
    
    参数:
        video_path: 视频文件路径
        audio_path: 音频文件路径
        output_path: 输出文件路径
        subtitle_path: 字幕文件路径，可选
        bgm_path: 背景音乐文件路径，可选
        options: 其他选项配置，可包含以下字段:
            - voice_volume: 人声音量，默认1.0
            - bgm_volume: 背景音乐音量，默认0.3
            - original_audio_volume: 原始音频音量，默认0.0
            - keep_original_audio: 是否保留原始音频，默认False
            - subtitle_font: 字幕字体，默认None，系统会使用默认字体
            - subtitle_font_size: 字幕字体大小，默认40
            - subtitle_color: 字幕颜色，默认白色
            - subtitle_bg_color: 字幕背景颜色，默认透明
            - subtitle_position: 字幕位置，可选值'bottom', 'top', 'center'，默认'bottom'
            - custom_position: 自定义位置
            - stroke_color: 描边颜色，默认黑色
            - stroke_width: 描边宽度，默认1
            - threads: 处理线程数，默认2
            - fps: 输出帧率，默认30
            - subtitle_enabled: 是否启用字幕，默认True
            
    返回:
        输出视频的路径
    """
    # 合并选项默认值
    if options is None:
        options = {}
    
    # 设置默认参数值 - 使用统一的音量配置
    voice_volume = options.get('voice_volume', AudioVolumeDefaults.VOICE_VOLUME)
    bgm_volume = options.get('bgm_volume', AudioVolumeDefaults.BGM_VOLUME)
    # 修复bug: 将原声音量默认值从0.0改为0.7，确保短剧解说模式下原片音量正常
    original_audio_volume = options.get('original_audio_volume', AudioVolumeDefaults.ORIGINAL_VOLUME)
    keep_original_audio = options.get('keep_original_audio', True)  # 默认保留原声
    subtitle_font = options.get('subtitle_font', '')
    subtitle_font_size = options.get('subtitle_font_size', 40)
    subtitle_color = options.get('subtitle_color', '#FFFFFF')
    subtitle_bg_color = options.get('subtitle_bg_color', 'transparent')
    subtitle_position = options.get('subtitle_position', 'bottom')
    custom_position = options.get('custom_position', 70)
    stroke_color = options.get('stroke_color', '#000000')
    stroke_width = options.get('stroke_width', 1)
    threads = options.get('threads', 2)
    fps = options.get('fps', 30)
    subtitle_enabled = options.get('subtitle_enabled', True)

    # 配置日志 - 便于调试问题
    logger.info(f"音量配置详情:")
    logger.info(f"  - 配音音量: {voice_volume}")
    logger.info(f"  - 背景音乐音量: {bgm_volume}")
    logger.info(f"  - 原声音量: {original_audio_volume}")
    logger.info(f"  - 是否保留原声: {keep_original_audio}")
    logger.info(f"字幕配置详情:")
    logger.info(f"  - 是否启用字幕: {subtitle_enabled}")
    logger.info(f"  - 字幕文件路径: {subtitle_path}")

    # 音量参数验证
    def validate_volume(volume, name):
        if not (AudioVolumeDefaults.MIN_VOLUME <= volume <= AudioVolumeDefaults.MAX_VOLUME):
            logger.warning(f"{name}音量 {volume} 超出有效范围 [{AudioVolumeDefaults.MIN_VOLUME}, {AudioVolumeDefaults.MAX_VOLUME}]，将被限制")
            return max(AudioVolumeDefaults.MIN_VOLUME, min(volume, AudioVolumeDefaults.MAX_VOLUME))
        return volume

    voice_volume = validate_volume(voice_volume, "配音")
    bgm_volume = validate_volume(bgm_volume, "背景音乐")
    original_audio_volume = validate_volume(original_audio_volume, "原声")

    # 处理透明背景色问题 - MoviePy 2.1.1不支持'transparent'值
    if subtitle_bg_color == 'transparent':
        subtitle_bg_color = None  # None在新版MoviePy中表示透明背景

    # 创建输出目录（如果不存在）
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"开始合并素材...")
    logger.info(f"  ① 视频: {video_path}")
    logger.info(f"  ② 音频: {audio_path}")
    if subtitle_path:
        logger.info(f"  ③ 字幕: {subtitle_path}")
    if bgm_path:
        logger.info(f"  ④ 背景音乐: {bgm_path}")
    logger.info(f"  ⑤ 输出: {output_path}")
    
    # 加载视频
    try:
        video_clip = VideoFileClip(video_path)
        logger.info(f"视频尺寸: {video_clip.size[0]}x{video_clip.size[1]}, 时长: {video_clip.duration}秒")
        
        # 提取视频原声(如果需要)
        original_audio = None
        if keep_original_audio and original_audio_volume > 0:
            try:
                original_audio = video_clip.audio
                if original_audio:
                    # 关键修复：只有当音量不为1.0时才进行音量调整，保持原声音量不变
                    if abs(original_audio_volume - 1.0) > 0.001:  # 使用小的容差值比较浮点数
                        original_audio = original_audio.with_effects([afx.MultiplyVolume(original_audio_volume)])
                        logger.info(f"已提取视频原声，音量调整为: {original_audio_volume}")
                    else:
                        logger.info("已提取视频原声，保持原始音量不变")
                else:
                    logger.warning("视频没有音轨，无法提取原声")
            except Exception as e:
                logger.error(f"提取视频原声失败: {str(e)}")
                original_audio = None
        
        # 移除原始音轨，稍后会合并新的音频
        video_clip = video_clip.without_audio()
        
    except Exception as e:
        logger.error(f"加载视频失败: {str(e)}")
        raise
    
    # 处理背景音乐和所有音频轨道合成
    audio_tracks = []

    # 智能音量调整（可选功能）
    if AudioVolumeDefaults.ENABLE_SMART_VOLUME and audio_path and os.path.exists(audio_path) and original_audio is not None:
        try:
            normalizer = AudioNormalizer()
            temp_dir = tempfile.mkdtemp()
            temp_original_path = os.path.join(temp_dir, "temp_original.wav")

            # 保存原声到临时文件进行分析
            original_audio.write_audiofile(temp_original_path, verbose=False, logger=None)

            # 计算智能音量调整
            tts_adjustment, original_adjustment = normalizer.calculate_volume_adjustment(
                audio_path, temp_original_path
            )

            # 应用智能调整，但保留用户设置的相对比例
            smart_voice_volume = voice_volume * tts_adjustment
            smart_original_volume = original_audio_volume * original_adjustment

            # 限制音量范围，避免过度调整
            smart_voice_volume = max(0.1, min(1.5, smart_voice_volume))
            smart_original_volume = max(0.1, min(2.0, smart_original_volume))

            voice_volume = smart_voice_volume
            original_audio_volume = smart_original_volume

            logger.info(f"智能音量调整 - TTS: {voice_volume:.2f}, 原声: {original_audio_volume:.2f}")

            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir)

        except Exception as e:
            logger.warning(f"智能音量分析失败，使用原始设置: {e}")

    # 先添加主音频（配音）
    if audio_path and os.path.exists(audio_path):
        try:
            voice_audio = AudioFileClip(audio_path).with_effects([afx.MultiplyVolume(voice_volume)])
            audio_tracks.append(voice_audio)
            logger.info(f"已添加配音音频，音量: {voice_volume}")
        except Exception as e:
            logger.error(f"加载配音音频失败: {str(e)}")

    # 添加原声（如果需要）
    if original_audio is not None:
        # 重新应用调整后的音量（因为original_audio已经应用了一次音量）
        # 计算需要的额外调整
        current_volume_in_original = 1.0  # original_audio中已应用的音量
        additional_adjustment = original_audio_volume / current_volume_in_original

        adjusted_original_audio = original_audio.with_effects([afx.MultiplyVolume(additional_adjustment)])
        audio_tracks.append(adjusted_original_audio)
        logger.info(f"已添加视频原声，最终音量: {original_audio_volume}")

    # 添加背景音乐（如果有）
    if bgm_path and os.path.exists(bgm_path):
        try:
            bgm_clip = AudioFileClip(bgm_path).with_effects([
                afx.MultiplyVolume(bgm_volume),
                afx.AudioFadeOut(3),
                afx.AudioLoop(duration=video_clip.duration),
            ])
            audio_tracks.append(bgm_clip)
            logger.info(f"已添加背景音乐，音量: {bgm_volume}")
        except Exception as e:
            logger.error(f"添加背景音乐失败: \n{traceback.format_exc()}")

    # 合成最终的音频轨道
    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        video_clip = video_clip.with_audio(final_audio)
        logger.info(f"已合成所有音频轨道，共{len(audio_tracks)}个")
    else:
        logger.warning("没有可用的音频轨道，输出视频将没有声音")
    
    # 处理字体路径
    font_path = None
    if subtitle_path and subtitle_font:
        font_path = os.path.join(utils.font_dir(), subtitle_font)
        if os.name == "nt":
            font_path = font_path.replace("\\", "/")
        logger.info(f"使用字体: {font_path}")
    
    # 处理视频尺寸
    video_width, video_height = video_clip.size
    
    # 字幕处理函数
    def create_text_clip(subtitle_item):
        """创建单个字幕片段"""
        phrase = subtitle_item[1]
        max_width = video_width * 0.9
        
        # 如果有字体路径，进行文本换行处理
        wrapped_txt = phrase
        txt_height = 0
        if font_path:
            wrapped_txt, txt_height = wrap_text(
                phrase, 
                max_width=max_width, 
                font=font_path, 
                fontsize=subtitle_font_size
            )
        
        # 创建文本片段
        try:
            _clip = TextClip(
                text=wrapped_txt,
                font=font_path,
                font_size=subtitle_font_size,
                color=subtitle_color,
                bg_color=subtitle_bg_color,  # 这里已经在前面处理过，None表示透明
                stroke_color=stroke_color,
                stroke_width=stroke_width,
            )
        except Exception as e:
            logger.error(f"创建字幕片段失败: {str(e)}, 使用简化参数重试")
            # 如果上面的方法失败，尝试使用更简单的参数
            _clip = TextClip(
                text=wrapped_txt,
                font=font_path,
                font_size=subtitle_font_size,
                color=subtitle_color,
            )
        
        # 设置字幕时间
        duration = subtitle_item[0][1] - subtitle_item[0][0]
        _clip = _clip.with_start(subtitle_item[0][0])
        _clip = _clip.with_end(subtitle_item[0][1])
        _clip = _clip.with_duration(duration)
        
        # 设置字幕位置
        if subtitle_position == "bottom":
            _clip = _clip.with_position(("center", video_height * 0.95 - _clip.h))
        elif subtitle_position == "top":
            _clip = _clip.with_position(("center", video_height * 0.05))
        elif subtitle_position == "custom":
            margin = 10
            max_y = video_height - _clip.h - margin
            min_y = margin
            custom_y = (video_height - _clip.h) * (custom_position / 100)
            custom_y = max(
                min_y, min(custom_y, max_y)
            )
            _clip = _clip.with_position(("center", custom_y))
        else:  # center
            _clip = _clip.with_position(("center", "center"))
            
        return _clip
        
    # 创建TextClip工厂函数
    def make_textclip(text):
        return TextClip(
            text=text,
            font=font_path,
            font_size=subtitle_font_size,
            color=subtitle_color,
        )
    
    # 处理字幕 - 修复字幕开关bug和空字幕文件问题
    if subtitle_enabled and subtitle_path:
        if is_valid_subtitle_file(subtitle_path):
            logger.info("字幕已启用，开始处理字幕文件")
            try:
                # 加载字幕文件
                sub = SubtitlesClip(
                    subtitles=subtitle_path,
                    encoding="utf-8",
                    make_textclip=make_textclip
                )

                # 创建每个字幕片段
                text_clips = []
                for item in sub.subtitles:
                    clip = create_text_clip(subtitle_item=item)
                    text_clips.append(clip)

                # 合成视频和字幕
                video_clip = CompositeVideoClip([video_clip, *text_clips])
                logger.info(f"已添加{len(text_clips)}个字幕片段")
            except Exception as e:
                logger.error(f"处理字幕失败: \n{traceback.format_exc()}")
                logger.warning("字幕处理失败，继续生成无字幕视频")
        else:
            logger.warning(f"字幕文件无效或为空: {subtitle_path}，跳过字幕处理")
    elif not subtitle_enabled:
        logger.info("字幕已禁用，跳过字幕处理")
    elif not subtitle_path:
        logger.info("未提供字幕文件路径，跳过字幕处理")
    
    # 导出最终视频
    try:
        video_clip.write_videofile(
            output_path,
            audio_codec="aac",
            temp_audiofile_path=output_dir,
            threads=threads,
            fps=fps,
        )
        logger.success(f"素材合并完成: {output_path}")
    except Exception as e:
        logger.error(f"导出视频失败: {str(e)}")
        raise
    finally:
        # 释放资源
        video_clip.close()
        del video_clip
    
    return output_path


def parse_timestamp_range(timestamp: str) -> tuple[float, float]:
    """
    解析时间戳范围 "00:00:00,000-00:00:05,900"

    Args:
        timestamp: 时间戳字符串

    Returns:
        (start_time, end_time) 单位：秒
    """
    from app.utils import utils

    parts = timestamp.split('-')
    if len(parts) != 2:
        raise ValueError(f"无效的时间戳格式: {timestamp}")

    start_time_str = parts[0].strip().replace(',', '.')
    end_time_str = parts[1].strip().replace(',', '.')

    start_time = utils.time_to_seconds(start_time_str)
    end_time = utils.time_to_seconds(end_time_str)

    return start_time, end_time


def merge_narration_to_full_video(
    video_path: str,
    narration_segments: list,
    output_path: str,
    mute_original_audio: bool = True,
    bgm_path: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    将解说音频和字幕叠加到完整原视频上（不裁剪视频）

    这是"真正意义上的逐帧解说"的核心函数。

    Args:
        video_path: 原视频文件路径（完整视频）
        narration_segments: 解说片段列表，每个包含：
            - timestamp: "00:00:00,000-00:00:05,900"
            - audio_path: 配音音频文件路径
            - subtitle_path: 字幕文件路径
        output_path: 输出文件路径
        mute_original_audio: 是否静音原声（在解说时段），默认True
        bgm_path: 背景音乐文件路径
        options: 其他选项配置

    Returns:
        输出视频的路径
    """
    # 合并选项默认值
    if options is None:
        options = {}

    # 设置默认参数值
    voice_volume = options.get('voice_volume', AudioVolumeDefaults.VOICE_VOLUME)
    bgm_volume = options.get('bgm_volume', AudioVolumeDefaults.BGM_VOLUME)
    original_audio_volume = options.get('original_audio_volume', 1.0 if not mute_original_audio else 0.0)
    subtitle_font = options.get('subtitle_font', '')
    subtitle_font_size = options.get('subtitle_font_size', 40)
    subtitle_color = options.get('subtitle_color', '#FFFFFF')
    subtitle_bg_color = options.get('subtitle_bg_color', None)
    subtitle_position = options.get('subtitle_position', 'bottom')
    custom_position = options.get('custom_position', 70)
    stroke_color = options.get('stroke_color', '#000000')
    stroke_width = options.get('stroke_width', 1)
    threads = options.get('threads', 2)
    subtitle_enabled = options.get('subtitle_enabled', True)

    logger.info(f"开始叠加解说到完整原视频...")
    logger.info(f"  ① 原视频: {video_path}")
    logger.info(f"  ② 解说片段数: {len(narration_segments)}")
    logger.info(f"  ③ 静音原声: {'是' if mute_original_audio else '否'}")
    logger.info(f"  ④ 输出: {output_path}")

    # 1. 加载完整原视频
    try:
        video_clip = VideoFileClip(video_path)
        logger.info(f"原视频时长: {video_clip.duration}秒")

        # 提取视频原声
        original_audio = None
        try:
            original_audio = video_clip.audio
            if original_audio:
                logger.info(f"已提取视频原声，音量: {original_audio_volume}")
            else:
                logger.warning("视频没有音轨，无法提取原声")
        except Exception as e:
            logger.error(f"提取视频原声失败: {str(e)}")
            original_audio = None

        # 移除原始音轨，稍后会合并新的音频
        video_clip = video_clip.without_audio()

    except Exception as e:
        logger.error(f"加载视频失败: {str(e)}")
        raise

    # 2. 创建配音音频片段（只在指定时间段）
    # 关键修复：先添加原声（如果存在），确保视频时长基于原声
    audio_tracks = []

    # 2.1 添加原声作为基础轨道（确保视频时长基于原声）
    if original_audio:
        # 如果需要按解说时段静音原声，使用分段拼接方式实现局部静音
        if mute_original_audio and narration_segments:
            logger.info("使用局部静音模式：在解说时段静音原声")
            # 解析所有解说时段并按时间排序
            mute_periods = []
            for segment in narration_segments:
                try:
                    start_time, end_time = parse_timestamp_range(segment['timestamp'])
                    mute_periods.append((start_time, end_time))
                except Exception as e:
                    logger.warning(f"解析静音时段失败: {str(e)}")
                    continue

            # 按开始时间排序
            mute_periods.sort(key=lambda x: x[0])
            logger.info(f"需要静音的时段数: {len(mute_periods)}")

            # 使用分段拼接方式构建原声（在解说时段插入静音片段）
            audio_segments = []
            last_end = 0.0

            for mute_start, mute_end in mute_periods:
                # 添加静音时段之前的部分（保留原声）
                if mute_start > last_end:
                    segment = original_audio.subclip(last_end, mute_start)
                    audio_segments.append(segment)
                    logger.debug(f"保留原声时段: {last_end:.2f}s - {mute_start:.2f}s")

                # 添加静音时段（音量为0）
                silent_duration = mute_end - mute_start
                silent_segment = original_audio.subclip(mute_start, mute_end).with_effects([afx.MultiplyVolume(0.0)])
                audio_segments.append(silent_segment)
                logger.debug(f"静音时段: {mute_start:.2f}s - {mute_end:.2f}s (时长{silent_duration:.2f}s)")

                last_end = mute_end

            # 添加最后一个静音时段之后的部分（保留原声）
            if last_end < original_audio.duration:
                segment = original_audio.subclip(last_end, original_audio.duration)
                audio_segments.append(segment)
                logger.debug(f"保留原声时段: {last_end:.2f}s - {original_audio.duration:.2f}s")

            # 将所有片段拼接起来
            if len(audio_segments) > 1:
                from moviepy import concatenate_audioclips
                original_audio = concatenate_audioclips(audio_segments)
                logger.info(f"原声已重新拼接（{len(audio_segments)}个片段）")
            elif len(audio_segments) == 1:
                original_audio = audio_segments[0]
                logger.info("原声无需分段拼接")
            else:
                logger.warning("没有音频片段，原声为空")

        # 应用整体音量
        if original_audio and original_audio_volume != 1.0:
            original_audio = original_audio.with_effects([afx.MultiplyVolume(original_audio_volume)])

        if original_audio:
            audio_tracks.append(original_audio)
            logger.info(f"已添加视频原声（基础轨道），最终音量: {original_audio_volume}")

    # 2.2 添加配音片段（只设置起始时间，不设置结束时间）
    for i, segment in enumerate(narration_segments, 1):
        timestamp = segment['timestamp']
        audio_path = segment['audio_path']

        try:
            # 解析时间戳
            start_time, end_time = parse_timestamp_range(timestamp)
            duration = end_time - start_time

            logger.info(f"处理片段 {i}/{len(narration_segments)}: {timestamp} ({duration:.2f}s)")

            # 加载配音音频
            voice_clip = AudioFileClip(audio_path)

            # 调整配音音量
            voice_clip = voice_clip.with_effects([afx.MultiplyVolume(voice_volume)])

            # 叠加配音到音频轨道
            voiced_clip = voice_clip.set_start(start_time)
            audio_tracks.append(voiced_clip)

        except Exception as e:
            logger.warning(f"处理片段 {i} 失败: {str(e)}")
            continue

    # 4. 添加BGM
    if bgm_path and os.path.exists(bgm_path):
        bgm_clip = AudioFileClip(bgm_path)
        bgm_clip = bgm_clip.with_effects([afx.MultiplyVolume(bgm_volume)])
        bgm_clip = bgm_clip.with_effects([afx.AudioLoop(duration=video_clip.duration)])
        audio_tracks.append(bgm_clip)
        logger.info(f"已添加背景音乐，音量: {bgm_volume}")

    # 5. 合成最终音频
    if audio_tracks:
        # 验证视频时长在处理音频前
        logger.info(f"合成音频前视频时长: {video_clip.duration}秒")

        final_audio = CompositeAudioClip(audio_tracks)
        video_clip = video_clip.without_audio()
        video_clip = video_clip.with_audio(final_audio)

        # 验证视频时长在处理音频后
        logger.info(f"合成音频后视频时长: {video_clip.duration}秒")

        logger.info("音频合成完成")
    else:
        logger.warning("没有音频轨道，视频将无声音")

    # 6. 叠加字幕（只在解说时段）
    if subtitle_enabled and narration_segments:
        logger.info("开始叠加字幕...")

        # 处理透明背景色问题 - MoviePy 2.1.1不支持'transparent'值
        if subtitle_bg_color == 'transparent':
            subtitle_bg_color = None  # None在新版MoviePy中表示透明背景

        for i, segment in enumerate(narration_segments, 1):
            subtitle_path = segment.get('subtitle_path')
            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    # 解析时间戳
                    start_time, end_time = parse_timestamp_range(segment['timestamp'])

                    logger.info(f"添加字幕 {i}: {segment['timestamp']}")

                    # 创建字幕剪辑
                    subtitles = SubtitlesClip(subtitle_path, fontsize=subtitle_font_size)
                    subtitles = subtitles.subclip(start_time, end_time)

                    # 叠加字幕到视频
                    video_clip = CompositeVideoClip([video_clip, subtitles])

                except Exception as e:
                    logger.warning(f"添加字幕 {i} 失败: {str(e)}")

    # 7. 输出视频
    logger.info(f"开始输出视频: {output_path}")
    logger.info(f"输出前视频时长: {video_clip.duration}秒")

    # 创建输出目录
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    video_clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        threads=threads,
        logger=None
    )

    # 验证输出视频时长
    try:
        output_video = VideoFileClip(output_path)
        logger.info(f"✅ 输出视频时长: {output_video.duration}秒")
        logger.success(f"视频生成成功: {output_path}")
        output_video.close()

        # 验证时长是否正确
        duration_diff = abs(output_video.duration - video_clip.duration)
        if duration_diff > 0.1:
            logger.warning(f"⚠️ 视频时长异常！处理前{video_clip.duration:.2f}s，处理后{output_video.duration:.2f}s，差异{duration_diff:.2f}s")
        else:
            logger.success(f"✅ 视频时长验证通过（{output_video.duration:.2f}s）")
    except Exception as e:
        logger.error(f"验证输出视频失败: {str(e)}")

    return output_path


 
def wrap_text(text, max_width, font="Arial", fontsize=60):
    """
    文本换行函数，使长文本适应指定宽度
    
    参数:
        text: 需要换行的文本
        max_width: 最大宽度（像素）
        font: 字体路径
        fontsize: 字体大小
        
    返回:
        换行后的文本和文本高度
    """
    # 创建ImageFont对象
    try:
        font_obj = ImageFont.truetype(font, fontsize)
    except:
        # 如果无法加载指定字体，使用默认字体
        font_obj = ImageFont.load_default()
    
    def get_text_size(inner_text):
        inner_text = inner_text.strip()
        left, top, right, bottom = font_obj.getbbox(inner_text)
        return right - left, bottom - top

    width, height = get_text_size(text)
    if width <= max_width:
        return text, height

    processed = True

    _wrapped_lines_ = []
    words = text.split(" ")
    _txt_ = ""
    for word in words:
        _before = _txt_
        _txt_ += f"{word} "
        _width, _height = get_text_size(_txt_)
        if _width <= max_width:
            continue
        else:
            if _txt_.strip() == word.strip():
                processed = False
                break
            _wrapped_lines_.append(_before)
            _txt_ = f"{word} "
    _wrapped_lines_.append(_txt_)
    if processed:
        _wrapped_lines_ = [line.strip() for line in _wrapped_lines_]
        result = "\n".join(_wrapped_lines_).strip()
        height = len(_wrapped_lines_) * height
        return result, height

    _wrapped_lines_ = []
    chars = list(text)
    _txt_ = ""
    for word in chars:
        _txt_ += word
        _width, _height = get_text_size(_txt_)
        if _width <= max_width:
            continue
        else:
            _wrapped_lines_.append(_txt_)
            _txt_ = ""
    _wrapped_lines_.append(_txt_)
    result = "\n".join(_wrapped_lines_).strip()
    height = len(_wrapped_lines_) * height
    return result, height


if __name__ == '__main__':
    merger_mp4 = '/Users/apple/Desktop/home/NarratoAI/storage/tasks/qyn2-2-demo/merger.mp4'
    merger_sub = '/Users/apple/Desktop/home/NarratoAI/storage/tasks/qyn2-2-demo/merged_subtitle_00_00_00-00_01_30.srt'
    merger_audio = '/Users/apple/Desktop/home/NarratoAI/storage/tasks/qyn2-2-demo/merger_audio.mp3'
    bgm_path = '/Users/apple/Desktop/home/NarratoAI/resource/songs/bgm.mp3'
    output_video = '/Users/apple/Desktop/home/NarratoAI/storage/tasks/qyn2-2-demo/combined_test.mp4'
    
    # 调用示例
    options = {
        'voice_volume': 1.0,            # 配音音量
        'bgm_volume': 0.1,              # 背景音乐音量
        'original_audio_volume': 1.0,   # 视频原声音量，0表示不保留
        'keep_original_audio': True,    # 是否保留原声
        'subtitle_enabled': True,       # 是否启用字幕 - 修复字幕开关bug
        'subtitle_font': 'MicrosoftYaHeiNormal.ttc',  # 这里使用相对字体路径，会自动在 font_dir() 目录下查找
        'subtitle_font_size': 40,
        'subtitle_color': '#FFFFFF',
        'subtitle_bg_color': None,      # 直接使用None表示透明背景
        'subtitle_position': 'bottom',
        'threads': 2
    }
    
    try:
        merge_materials(
            video_path=merger_mp4,
            audio_path=merger_audio,
            subtitle_path=merger_sub,
            bgm_path=bgm_path,
            output_path=output_video,
            options=options
        )
    except Exception as e:
        logger.error(f"合并素材失败: \n{traceback.format_exc()}")
