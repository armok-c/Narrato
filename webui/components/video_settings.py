import streamlit as st
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
    # 关键修复：从 session_state 获取之前的值，避免每次重置
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
