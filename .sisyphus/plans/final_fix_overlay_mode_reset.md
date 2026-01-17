# 修复叠加配音模式被重置的问题

## 🐛 问题

从日志看出：
```
clip_video_unified - 开始统一视频裁剪...
merge_clip_videos - 准备合并 11 个视频片段
merge_materials - 视频时长: 49.83秒  ❌
```

**根本原因**：
- 虽然用户勾选了"叠加配音模式"
- 但 Streamlit 每次重新渲染时，`overlay_mode` 被重置为 `False`（默认值）
- 导致 `is_auto_mode and overlay_mode` 条件为 False
- 系统使用了 `start_subclip_unified`（裁剪模式），而不是 `start_overlay_narration`（叠加配音模式）

---

## ✅ 修复方案

### 修复：保留 `overlay_mode` 的状态

**文件**: `webui/components/video_settings.py`

**修改前**:
```python
overlay_mode = st.checkbox(
    tr("叠加配音模式（保留完整原视频）"),
    value=False,  # ❌ 每次都是 False
    help="在原视频上叠加配音和字幕，不裁剪视频"
)
st.session_state['overlay_mode'] = overlay_mode
```

**修改后**:
```python
overlay_mode = st.checkbox(
    tr("叠加配音模式（保留完整原视频）"),
    value=st.session_state.get('overlay_mode', False),  # ✅ 使用已保存的值
    help="在原视频上叠加配音和字幕，不裁剪视频"
)
st.session_state['overlay_mode'] = overlay_mode
```

**同时修复 `mute_original_audio`**:
```python
if overlay_mode:
    mute_original_audio = st.checkbox(
        tr("静音原声（在解说时段）"),
        value=st.session_state.get('mute_original_audio', True),  # ✅ 使用已保存的值
        help="在解说时段静音原声，保持配音清晰"
    )
    st.session_state['mute_original_audio'] = mute_original_audio
else:
    # 如果取消叠加模式，重置静音选项
    if 'mute_original_audio' in st.session_state:
        del st.session_state['mute_original_audio']
```

---

## 🎯 修复效果

### 修复前

```
1. 用户勾选"叠加配音模式"
   overlay_mode = True
   
2. Streamlit 重新渲染（任何交互都会触发）
   overlay_mode = False  ❌  ← 被重置
   
3. 点击"生成视频"
   is_auto_mode and overlay_mode = True and False  ❌
   使用 start_subclip_unified（裁剪模式）
   
4. 生成视频：49.83秒  ❌
```

### 修复后

```
1. 用户勾选"叠加配音模式"
   overlay_mode = True
   st.session_state['overlay_mode'] = True ✅
   
2. Streamlit 重新渲染
   value=st.session_state.get('overlay_mode', False)  ✅
   overlay_mode = True
   
3. 点击"生成视频"
   is_auto_mode and overlay_mode = True and True ✅
   使用 start_overlay_narration（叠加配音模式）
   
4. 生成视频：73.7秒  ✅
```

---

## 🚀 测试流程

1. 进入逐帧解说页面
2. 选择视频文件（73.7秒）
3. 填写视频主题
4. 点击"AI生成画面解说脚本"
5. 点击"保存脚本"
6. 跳转到"选择/上传脚本"页面
7. **勾选"叠加配音模式（保留完整原视频）"**
8. **勾选"静音原声（在解说时段）"**（默认已勾选）
9. **点击"生成视频"**
10. **验证**：
    - 日志中应该有 `开始叠加解说任务`（不是 `开始统一视频裁剪`）
    - 日志中应该有 `原视频时长: 73.7秒`
    - 日志中应该有 `输出视频时长: 73.7秒`
    - 生成视频时长应该是 73.7 秒

---

## ✅ 修复完成！

所有修改已完成，叠加配音模式现在应该可以正确工作了。
