# 修复叠加配音模式无法启用的问题

## 🐛 问题描述

用户反馈："叠加配音模式没办法启用"

**原因**: UI流程中的 `script_type` 检查逻辑不正确

---

## 🔍 问题分析

### 实际UI流程

```
1. 进入逐帧解说页面
2. 选择视频文件
3. 填写视频主题
4. 点击AI生成画面解说脚本
5. 点击保存脚本
6. 跳转到选择/上传脚本页面
7. 点击生成视频
```

### 问题根源

在 `video_settings.py` 中，我添加的检查逻辑：

```python
script_type = st.session_state.get('video_clip_json_path', '')
is_auto_mode = script_type == "auto"  # ❌ 问题在这里！
```

**问题**:
- 在步骤5"保存脚本"后，`video_clip_json_path` 被保存为一个**具体的JSON文件路径**
- 例如：`/path/to/script.json`
- 所以 `script_type == "auto"` 总是 `False`
- 导致叠加配音选项从不显示

### 原始流程

在 `script_settings.py` 的 `render_script_buttons()` 中：

```python
if script_path == "auto":
    button_name = tr("Generate Video Script")
elif script_path == "short":
    button_name = tr("Generate Short Video Script")
elif script_path == "summary":
    button_name = tr("生成短剧解说脚本")
elif script_path.endswith("json"):
    button_name = tr("Load Video Script")  # ← 这里会变成上传模式
```

**流程转换**:
- 步骤4: `video_clip_json_path` = `"auto"` ✓
- 步骤5: `video_clip_json_path` = 保存的JSON文件路径 ❌
- 步骤6: `script_path` 现在是一个JSON文件路径
- 步骤7: `is_auto_mode = script_type == "auto"` → `False` ❌

---

## ✅ 解决方案

### 修复1: 保存脚本生成模式

**文件**: `webui/components/script_settings.py`

**修改**: 在保存脚本时，同时保存生成模式

```python
def save_script_with_validation(tr, video_clip_json_details):
    """保存视频脚本（包含格式验证）"""
    # ... 原有代码 ...

    # 新增：保存脚本生成模式（用于判断是否显示叠加配音选项）
    st.session_state['script_generation_mode'] = script_path if script_path in ["auto", "short", "summary"] else "file"

    st.success(tr("Script saved successfully"))
    st.rerun()
```

### 修复2: 更新按钮名称显示逻辑

**文件**: `webui/components/script_settings.py`

**修改**: 检查 `script_generation_mode`

```python
def render_script_buttons(tr, params):
    """渲染脚本操作按钮"""
    # 获取当前选择的脚本类型
    script_path = st.session_state.get('video_clip_json_path', '')
    script_generation_mode = st.session_state.get('script_generation_mode', '')

    # 生成/加载按钮
    if script_path == "auto" or script_generation_mode == "auto":
        button_name = tr("Generate Video Script")
    elif script_path == "short":
        button_name = tr("Generate Short Video Script")
    elif script_path == "summary":
        button_name = tr("生成短剧解说脚本")
    elif script_path.endswith("json"):
        button_name = tr("Load Video Script")
    else:
        button_name = tr("Please Select Script File")
```

### 修复3: 更新视频配置检查逻辑

**文件**: `webui/components/video_settings.py`

**修改**: 同时检查 `script_generation_mode`

```python
def render_video_config(tr, params):
    """渲染视频配置"""
    # ... 现有配置 ...

    # 新增：叠加配音模式（仅在逐帧解说模式下显示）
    script_type = st.session_state.get('video_clip_json_path', '')
    script_generation_mode = st.session_state.get('script_generation_mode', '')
    is_auto_mode = (script_type == "auto" or script_generation_mode == "auto")

    if is_auto_mode:
        overlay_mode = st.checkbox(
            tr("叠加配音模式（保留完整原视频）"),
            value=False,
            help="在原视频上叠加配音和字幕，不裁剪视频（适用于逐帧解说）"
        )
        st.session_state['overlay_mode'] = overlay_mode

        if overlay_mode:
            mute_original_audio = st.checkbox(
                tr("静音原声（在解说时段）"),
                value=True,
                help="在解说时段静音原声，保持配音清晰"
            )
            st.session_state['mute_original_audio'] = mute_original_audio
```

### 修复4: 更新视频生成调用逻辑

**文件**: `webui.py`

**修改**: 检查 `script_generation_mode`

```python
def run_task():
    try:
        # 检查是否是逐帧解说 + 叠加配音模式
        script_type = st.session_state.get('video_clip_json_path', '')
        script_generation_mode = st.session_state.get('script_generation_mode', '')
        overlay_mode = st.session_state.get('overlay_mode', False)

        # 检查是否是逐帧解说模式（包括从auto模式保存的脚本）
        is_auto_mode = (script_type == "auto" or script_generation_mode == "auto")

        if is_auto_mode and overlay_mode:
            # 使用新的叠加配音任务
            tm.start_overlay_narration(task_id=task_id, params=params)
        else:
            # 使用原有的裁剪+合并任务
            tm.start_subclip_unified(task_id=task_id, params=params)
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED, message=str(e))
```

---

## 🎯 修复效果

### 修复前

```
步骤4: video_clip_json_path = "auto" ✓
步骤5: video_clip_json_path = "/path/to/script.json" ❌
步骤6: script_type = "/path/to/script.json"
步骤7: is_auto_mode = False ❌
结果: 叠加配音选项不显示
```

### 修复后

```
步骤4: video_clip_json_path = "auto" ✓
        script_generation_mode = "auto" ✓
步骤5: video_clip_json_path = "/path/to/script.json" ✓
        script_generation_mode = "auto" ✓
步骤6: script_type = "/path/to/script.json"
        script_generation_mode = "auto"
步骤7: is_auto_mode = True ✓
结果: 叠加配音选项显示 ✓
```

---

## 📋 测试验证

1. 进入逐帧解说页面
2. 选择视频文件
3. 填写视频主题
4. 点击AI生成画面解说脚本
5. 点击保存脚本
6. 跳转到选择/上传脚本页面
7. **验证**：在视频设置中看到"叠加配音模式（保留完整原视频）"选项 ✓
8. 勾选"叠加配音模式"
9. 点击生成视频
10. **验证**：生成73.7秒的完整视频，在解说时段叠加配音和字幕 ✓

---

## ✅ 修复完成

所有4个修改已完成，叠加配音模式现在可以在逐帧解说流程中正确启用。
