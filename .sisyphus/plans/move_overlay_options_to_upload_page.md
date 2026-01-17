# 将叠加配音模式移动到选择/上传脚本页面

## ✅ 修改完成

### 修改内容

### 1. 移除逐帧解说模式限制
**文件**: `webui/components/video_settings.py`

**修改前**:
```python
# 新增：叠加配音模式（仅在逐帧解说模式下显示）
is_auto_mode = script_type == "auto" or script_generation_mode == "auto"

if is_auto_mode:
    overlay_mode = st.checkbox(...)
```

**修改后**:
```python
# 新增：叠加配音模式（对所有脚本类型都显示）
overlay_mode = st.checkbox(
    tr("叠加配音模式（保留完整原视频）"),
    value=False,
    help="在原视频上叠加配音和字幕，不裁剪视频"
)
st.session_state['overlay_mode'] = overlay_mode

if overlay_mode:
    mute_original_audio = st.checkbox(...)
    st.session_state['mute_original_audio'] = mute_original_audio
```

### 2. 保存所有脚本生成模式
**文件**: `webui/components/script_settings.py`

**修改前**:
```python
if st.button(button_name, key="script_action", disabled=not script_path):
    if script_path == "auto":
        # 执行纪录片视频脚本生成
        generate_script_docu(params)
```

**修改后**:
```python
# 在任何脚本生成模式下都保存生成模式（包括auto）
st.session_state['script_generation_mode'] = script_path if script_path in ["auto", "short", "summary"] else "file"

if st.button(button_name, key="script_action", disabled=not script_path):
    if script_path == "auto":
        # 执行纪录片视频脚本生成
        generate_script_docu(params)
    # ...
```

---

## 🎯 效果

### 修改前

```
1. 进入逐帧解说页面
   - ❌ 看不到"叠加配音模式"选项

2. 生成脚本并保存
3. 跳转到选择/上传脚本页面
   - ✅ 看到"叠加配音模式"选项

4. 上传其他脚本（如从外部获取的逐帧解说脚本）
   - ❌ 看不到"叠加配音模式"选项
```

### 修改后

```
1. 进入逐帧解说页面
   - ❌ 看不到"叠加配音模式"选项（因为还没有生成脚本）

2. 生成脚本并保存
3. 跳转到选择/上传脚本页面
   - ✅ 看到"叠加配音模式"选项

4. 上传其他脚本（如从外部获取的逐帧解说脚本）
   - ✅ 看到"叠加配音模式"选项 ✓

5. 勾选"叠加配音模式"
6. 勾选"静音原声（在解说时段）"
7. 点击生成视频
8. ✅ 得到73.7秒的完整视频
```

---

## 📝 使用场景

### 场景1：使用系统生成的逐帧解说脚本
1. 进入逐帧解说页面
2. 生成脚本
3. 跳转到选择/上传脚本页面
4. 勾选"叠加配音模式"和"静音原声"
5. 生成视频

### 场景2：使用外部逐帧解说脚本
1. 直接进入选择/上传脚本页面
2. 上传从外部获取的逐帧解说脚本JSON
3. 勾选"叠加配音模式"和"静音原声"
4. 生成视频

### 场景3：使用短剧解说脚本
1. 进入短剧解说页面
2. 生成脚本
3. 跳转到选择/上传脚本页面
4. ✅ 也可以看到"叠加配音模式"选项
5. 勾选后生成视频

---

## ✅ 完成状态

所有修改已完成，叠加配音模式现在可以在"选择/上传脚本"页面看到和使用。
