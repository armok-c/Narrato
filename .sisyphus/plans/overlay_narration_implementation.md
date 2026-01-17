# 逐帧解说叠加配音功能 - 实施计划

## 📋 需求确认

- **功能范围**: 只有逐帧解说（AUTO_MODE）支持叠加配音模式
- **新增选项**: "解说时段是否静音原声"（默认：静音）
- **核心要求**: 
  - ✅ 保留原视频所有内容（73.7秒完整）
  - ✅ 只在需要解说的片段叠加配音和字幕
  - ✅ 不需要解说的片段保持纯原声
  - ❌ 不裁剪视频

---

## 🔧 实施步骤

### 第一步：添加叠加配音核心函数

**文件**: `app/services/generate_video.py`

**任务**: 添加 `merge_narration_to_full_video()` 和 `parse_timestamp_range()` 函数

**位置**: 插入到 `merge_materials()` 函数之后（约第410行之后）

**代码**:

```python
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
    narration_segments: List[Dict[str, Any]],
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
                # 如果需要静音原声，设置为0.0
                if mute_original_audio:
                    original_audio_volume = 0.0
                    logger.info("已设置原声音量: 0.0 (静音)")
                else:
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
    audio_tracks = []
    
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
            
            # 将配音放置在正确的时间段
            voiced_clip = voice_clip.set_start(start_time).set_end(end_time)
            audio_tracks.append(voiced_clip)
            
        except Exception as e:
            logger.warning(f"处理片段 {i} 失败: {str(e)}")
            continue
    
    # 3. 添加原声（如果存在）
    if original_audio and original_audio_volume > 0:
        audio_tracks.append(original_audio)
        logger.info(f"已添加视频原声，最终音量: {original_audio_volume}")
    
    # 4. 添加BGM
    if bgm_path and os.path.exists(bgm_path):
        bgm_clip = AudioFileClip(bgm_path)
        bgm_clip = bgm_clip.with_effects([afx.MultiplyVolume(bgm_volume)])
        bgm_clip = bgm_clip.with_effects([afx.AudioLoop(duration=video_clip.duration)])
        audio_tracks.append(bgm_clip)
        logger.info(f"已添加背景音乐，音量: {bgm_volume}")
    
    # 5. 合成最终音频
    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        video_clip = video_clip.with_audio(final_audio)
        logger.info("音频合成完成")
    else:
        logger.warning("没有音频轨道，视频将无声音")
    
    # 6. 叠加字幕（只在解说时段）
    if subtitle_enabled and narration_segments:
        logger.info("开始叠加字幕...")
        
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
    
    logger.success(f"视频生成成功: {output_path}")
    return output_path
```

---

### 第二步：添加新的任务函数

**文件**: `app/services/task.py`

**任务**: 添加 `start_overlay_narration()` 函数

**位置**: 插入到文件末尾（约第460行之后）

**代码**:

```python
def start_overlay_narration(task_id: str, params: VideoClipParams):
    """
    叠加解说到完整原视频（不裁剪视频）
    
    这是"真正意义上的逐帧解说"的新任务类型。
    
    只在逐帧解说（AUTO_MODE）下使用。
    
    Args:
        task_id: 任务ID
        params: 视频参数
    """
    logger.info(f"\n\n## 开始叠加解说任务: {task_id}")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=0)
    
    """
    1. 加载剪辑脚本
    """
    logger.info("\n\n## 1. 加载视频脚本")
    video_script_path = path.join(params.video_clip_json_path)
    
    if path.exists(video_script_path):
        with open(video_script_path, "r", encoding="utf-8") as f:
            list_script = json.load(f)
            video_list = [i['narration'] for i in list_script]
            video_ost = [i['OST'] for i in list_script]
            time_list = [i['timestamp'] for i in list_script]
            
            logger.debug(f"解说完整脚本: \n{video_list}")
            logger.debug(f"解说 OST 列表: \n{video_ost}")
            logger.debug(f"解说时间戳列表: \n{time_list}")
    else:
        raise ValueError("解说脚本文件不存在！")
    
   
