# IDEA.md - Azur Lane Assets

## 项目定位
对《碧蓝航线》的 Unity AssetBundle 资源包进行解包、分类、导出与还原，
输出可用于查看和分析的图片、音频、Live2D、Spine 动画及元数据。

## 核心目标
1. 扫描索引全部 AssetBundle（~8.7 万文件 / 26.6 GB）
2. 批量导出立绘、背景图、UI/图标
3. 还原 Live2D 模型（moc3 / model3.json / 贴图 / motion）
4. 提取 Spine 动态立绘并提供 WebGL 预览
5. 解码 CRIWARE 音频为 WAV（BGM / CV / SE）
6. 合成多部件立绘（ALPA 算法），修复角色与背景的层级/位置关系

## 技术栈
Python 3.13 + UnityPy 1.25.0 + Pillow / vgmstream / ffmpeg；
外部工具：AssetStudioGUI / ALPA / Live2DViewerEX

## 进度与下一步
实时状态见 `PROJECT_STATUS.md`（跨会话对接用）。
