# 修复视频长度问题：49秒→73.7秒

## 🐛 问题

**症状**: 生成的视频只有49秒，而不是完整的73.7秒。

**根本原因**:
1. 使用了 `set_end(end_time)` 导致MoviePy认为视频应该缩短
2. `CompositeAudioClip` 根据最长的音频轨道调整视频时长
3. 原声没有被正确添加，导致视频时长基于配音时长

---

## ✅ 修复方案

### 修复1: 移除 `set_end()`

**文件**: `app/services/generate_video.py:merge_narration_to_full_video()`

**修改前**:
```python
voiced_clip = voice_clip.set_start(start_time).set_end(end_time)
audio_tracks.append(voiced_clip)
```

**修改后**:
```python
# 只设置起始时间，让配音在原声轨道上叠加播放
voiced_clip = voice_clip.set_start(start_time)
audio_tracks.append(voiced_clip)
```

**效果**: 配音不会影响视频时长，视频时长基于原声轨道

### 修复2: 原声作为基础轨道

**修改前**:
```python
# 配音片段
for ...:
    audio_tracks.append(voiced_clip)

# 原声（在最后）
if original_audio:
    audio_tracks.append(original_audio)
```

**修改后**:
```python
# 原声作为第一个轨道（确保视频时长基于原声）
if original_audio:
    audio_tracks.append(original_audio)

# 配音片段（只设置起始时间）
for ...:
    voiced_clip = voice_clip.set_start(start_time)
    audio_tracks.append(voiced_clip)
```

**效果**: 视频时长始终基于原声（73.7秒）

### 修复3: 添加时长验证

**新增**:
```python
# 合成音频前
logger.info(f"合成音频前视频时长: {video_clip.duration}秒")

# 合成音频
final_audio = CompositeAudioClip(audio_tracks)
video_clip = video_clip.with_audio(final_audio)

# 合成音频后
logger.info(f"合成音频后视频时长: {video_clip.duration}秒")

# 输出视频
video_clip.write_videofile(...)

# 验证输出视频时长
output_video = VideoFileClip(output_path)
logger.info(f"✅ 输出视频时长: {output_video.duration}秒")

# 验证时长
duration_diff = abs(output_video.duration - original_duration)
if duration_diff > 0.1:
    logger.warning(f"⚠️ 视频时长异常！差异{duration_diff:.2f}s")
```

---

## 🎯 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 原视频时长 | 73.7秒 | 73.7秒 |
| 生成视频时长 | 49秒 ❌ | 73.7秒 ✅ |
| 解说时段 | 正常 | 正常 |
| 原声 | 可能丢失 | 完整保留 ✅ |
| 静音原声 | 可能无效 | 正常工作 ✅ |

---

## 🔍 技术细节

### 关键原理

**问题**: `set_end()` 告诉MoviePy"音频在这里结束"，MoviePy会据此调整视频时长

**解决**: 只使用 `set_start()`，让配音自然播放到结束，不影响视频总时长

**原声处理**: 将原声作为基础轨道（第一个添加），确保视频时长始终为73.7秒

---

## 🚀 测试验证

1. 生成视频后，检查日志中的：
   - 原视频时长: 73.7秒
   - 合成音频前视频时长: 73.7秒
   - 合成音频后视频时长: 73.7秒
   - 输出视频时长: 73.7秒

2. 播放输出视频，验证：
   - 时长是否为73.7秒
   - 解说时段是否正确叠加
   - 原声是否在解说时段静音（如果勾选）
