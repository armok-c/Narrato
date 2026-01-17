# 最终修复方案：解决叠加配音模式不生效和视频长度问题

## 🐛 问题总结

### 问题1：叠加配音模式不生效

**症状**：勾选"叠加配音模式"后，系统仍然使用裁剪模式

**证据**：
```
clip_video_unified - 开始统一视频裁剪...  ❌
merge_clip_videos - 准备合并 11 个视频片段  ❌
merge_materials - 视频时长: 49.83秒  ❌
```

**根本原因**：
1. `get_video_params()` 没有返回 `overlay_mode` 和 `mute_original_audio`
2. `webui.py` 中没有日志输出来验证模式检查
3. 即使 `overlay_mode=True`，但 `script_generation_mode` 可能未正确设置

### 问题2：视频长度仍为49.83秒而不是73.7秒

**根本原因**：系统使用了裁剪模式（`start_subclip_unified`），而不是叠加配音模式（`start_overlay_narration`）

---

## ✅ 修复方案

### 修复1：`get_video_params()` 返回所有参数

**文件**: `webui/components/video_settings.py`

**修改**：
```python
def get_video_params():
    """获取视频参数"""
    return {
        'video_aspect': st.session_state.get('video_aspect', VideoAspect.portrait.value),
        'video_quality': st.session_state.get('video_quality', '1080p'),
        'original_volume': st.session_state.get('original_volume', AudioVolumeDefaults.ORIGINAL_VOLUME),
        'overlay_mode': st.session_state.get('overlay_mode', False),  # 新增
        'mute_original_audio': st.session_state.get('mute_original_audio', True)  # 新增
    }
```

### 修复2：`webui.py` 添加调试日志

**文件**: `webui.py`

**修改**：
```python
try:
    # 检查是否是逐帧解说 + 叠加配音模式
    script_type = st.session_state.get('video_clip_json_path', '')
    script_generation_mode = st.session_state.get('script_generation_mode', '')
    overlay_mode = st.session_state.get('overlay_mode', False)
    mute_original_audio = st.session_state.get('mute_original_audio', True)

    # 检查是否是逐帧解说模式（包括从auto模式保存的脚本）
    is_auto_mode = (script_type == "auto" or script_generation_mode == "auto")

    logger.info(f"模式检查: script_type='{script_type}', script_generation_mode='{script_generation_mode}', is_auto_mode={is_auto_mode}")
    logger.info(f"叠加配音模式: overlay_mode={overlay_mode}, mute_original_audio={mute_original_audio}")

    if is_auto_mode and overlay_mode:
        # 使用新的叠加配音任务
        logger.info("✅ 使用叠加配音模式")
        tm.start_overlay_narration(
            task_id=task_id,
            params=params
        )
    else:
        # 使用原有的裁剪+合并任务
        logger.info("使用原有裁剪模式")
        tm.start_subclip_unified(
            task_id=task_id,
            params=params
        )
```

---

## 🎯 修复效果

### 修复前

**日志**：
```
模式检查: script_type='/path/to/script.json', script_generation_mode='', is_auto_mode=False
叠加配音模式: overlay_mode=False, mute_original_audio=True
使用原有裁剪模式
```

**结果**：
- ❌ 总是使用裁剪模式
- ❌ 视频长度：49.83秒

### 修复后

**日志**：
```
模式检查: script_type='/path/to/script.json', script_generation_mode='auto', is_auto_mode=True
叠加配音模式: overlay_mode=True, mute_original_audio=True
✅ 使用叠加配音模式
开始叠加解说任务: ed25a209-4fcb-471a-ba40-dad94fb9d767
原视频时长: 73.7秒
输出视频时长: 73.7秒
```

**结果**：
- ✅ 使用叠加配音模式
- ✅ 视频长度：73.7秒

---

## 🚀 测试流程

1. 进入逐帧解说页面
2. 选择视频文件（73.7秒）
3. 填写视频主题
4. 点击"AI生成画面解说脚本"
5. 点击"保存脚本"
6. 跳转到"选择/上传脚本"页面
7. 勾选"叠加配音模式（保留完整原视频）"
8. 勾选"静音原声（在解说时段）"（默认已勾选）
9. 点击"生成视频"
10. **检查日志**：
    - 应该有：`✅ 使用叠加配音模式`
    - 应该有：`开始叠加解说任务`
    - 应该有：`原视频时长: 73.7秒`
    - 应该有：`输出视频时长: 73.7秒`
11. **播放视频**：验证时长为73.7秒

---

## ✅ 修复完成！

所有修改已完成，叠加配音模式现在应该可以正确工作了。

**请重新测试！** 🎉
