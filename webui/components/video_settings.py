import streamlit as st
from loguru import logger
from app.models.schema import VideoClipParams, VideoAspect, AudioVolumeDefaults


def render_video_panel(tr):
    """渲染视频配置面板"""
    with st.container(border=True):
        st.write(tr("Video Settings"))
        params = VideoClipParams()
        render_video_config(tr, params)


def render_video_config(tr, params):
    """渲染视频配置"""
    # 视频比例
    video_aspect_ratios = [
        (tr("Portrait"), VideoAspect.portrait.value),
        (tr("Landscape"), VideoAspect.landscape.value),
    ]
    selected_index = st.selectbox(
        tr("Video Ratio"),
        options=range(len(video_aspect_ratios)),
        format_func=lambda x: video_aspect_ratios[x][0],
    )
    params.video_aspect = VideoAspect(video_aspect_ratios[selected_index][1])
    st.session_state['video_aspect'] = params.video_aspect.value

    # 视频画质
    video_qualities = [
        ("4K (2160p)", "2160p"),
        ("2K (1440p)", "1440p"),
        ("Full HD (1080p)", "1080p"),
        ("HD (720p)", "720p"),
        ("SD (480p)", "480p"),
    ]
    quality_index = st.selectbox(
        tr("Video Quality"),
        options=range(len(video_qualities)),
        format_func=lambda x: video_qualities[x][0],
        index=2  # 默认选择 1080p
    )
    st.session_state['video_quality'] = video_qualities[quality_index][1]

    # 原声音量 - 使用统一的默认值
    params.original_volume = st.slider(
        tr("Original Volume"),
        min_value=AudioVolumeDefaults.MIN_VOLUME,
        max_value=AudioVolumeDefaults.MAX_VOLUME,
        value=AudioVolumeDefaults.ORIGINAL_VOLUME,
        step=0.01,
        help=tr("Adjust the volume of the original audio")
    )
    st.session_state['original_volume'] = params.original_volume

    # 新增：叠加配音模式（对所有脚本类型都显示）
    # 强制逻辑：逐帧解说模式强制启用叠加配音
    # 检测方式：通过session_state的script_generation_mode或通过脚本的OST值判断
    script_generation_mode = st.session_state.get('script_generation_mode', '')
    is_auto_from_session = (script_generation_mode == "auto")
    is_auto_from_ost = is_auto_script_from_ost()  # 新增：通过OST值检测逐帧解说脚本
    is_auto_mode = is_auto_from_session or is_auto_from_ost  # 两种方式都支持

    # 如果是逐帧解说模式，强制启用叠加配音，并且禁用取消选项
    if is_auto_mode:
        overlay_mode = True
        st.session_state['overlay_mode'] = True
        st.checkbox(
            tr("叠加配音模式（保留完整原视频）"),
            value=True,
            disabled=True,
            help="逐帧解说模式已自动启用叠加配音功能（不可禁用）"
        )
    else:
        # 非逐帧解说模式，允许用户手动选择
        overlay_mode = st.checkbox(
            tr("叠加配音模式（保留完整原视频）"),
            value=st.session_state.get('overlay_mode', False),  # 使用已保存的值
            help="在原视频上叠加配音和字幕，不裁剪视频"
        )
        st.session_state['overlay_mode'] = overlay_mode

    # 新增：静音原声（仅在叠加模式下显示）
    if overlay_mode:
        mute_original_audio = st.checkbox(
            tr("静音原声（在解说时段）"),
            value=st.session_state.get('mute_original_audio', True),  # 使用已保存的值
            help="在解说时段静音原声，保持配音清晰"
        )
        st.session_state['mute_original_audio'] = mute_original_audio
    else:
        # 如果取消叠加模式，重置静音选项
        if 'mute_original_audio' in st.session_state:
            del st.session_state['mute_original_audio']



def get_video_params():
    """获取视频参数"""
    return {
        'video_aspect': st.session_state.get('video_aspect', VideoAspect.portrait.value),
        'video_quality': st.session_state.get('video_quality', '1080p'),
        'original_volume': st.session_state.get('original_volume', AudioVolumeDefaults.ORIGINAL_VOLUME),
        'overlay_mode': st.session_state.get('overlay_mode', False),  # 新增
        'mute_original_audio': st.session_state.get('mute_original_audio', True)  # 新增
    }


def is_auto_script_from_ost():
    """
    检查当前脚本是否为逐帧解说模式（通过OST字段判断）

    支持两种数据源：
    1. st.session_state['video_clip_json']：内存中的脚本数据
    2. st.session_state['video_clip_json'] 为空时，从 video_clip_json_path 文件读取
    """
    # 尝试从 session_state 获取
    video_clip_json = st.session_state.get('video_clip_json', [])

    # 如果内存中没有，尝试从文件路径读取
    if not video_clip_json or len(video_clip_json) == 0:
        video_clip_json_path = st.session_state.get('video_clip_json_path', '')
        if isinstance(video_clip_json_path, str) and video_clip_json_path:
            try:
                import json
                import os
                if os.path.exists(video_clip_json_path):
                    with open(video_clip_json_path, 'r', encoding='utf-8') as f:
                        video_clip_json = json.load(f)
                        logger.info(f"从文件加载脚本数据: {video_clip_json_path}, 片段数: {len(video_clip_json)}")
            except Exception as e:
                logger.warning(f"从文件加载脚本失败: {str(e)}")

    if not video_clip_json or len(video_clip_json) == 0:
        return False

    # 检查所有片段的OST值：如果所有片段的OST都等于2，则是逐帧解说模式
    all_ost_values = [segment.get('OST', 0) for segment in video_clip_json]
    # OST=2 表示保留原声和配音（逐帧解说模式生成的脚本）
    if all_ost_values and all(ost == 2 for ost in all_ost_values):
        logger.info(f"检测到逐帧解说脚本：所有{len(video_clip_json)}个片段的OST值均为2")
        return True

    logger.debug(f"脚本OST值检查：OST值={[segment.get('OST', 0) for segment in video_clip_json]}")
    return False
