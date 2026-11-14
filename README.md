# 高考必背3600词 · ClassIsland 插件

在 ClassIsland 主界面轮播高考英语词汇，**每次显示 2 个单词**，每个单词包含：

- 英文单词
- 词性（n. / v. / adj. / prep. …）
- 中文释义

词性与中文释义合并显示在单词下方，适配 ClassIsland 约 65px 高的组件行。

插件完全离线运行：只读取本地 XML，不发送任何网络请求。

> 组件本身不设背景，会跟随 ClassIsland 的明暗主题；不显示标题、进度和音标，把高度留给中文释义。

## 功能

- 两词一屏，左右并排显示，适合放在 ClassIsland 主界面的组件行中
- 英文单词 + 词性/中文释义，两行紧凑布局
- 可设置轮播间隔（3–600 秒）
- 随机顺序 / 字母顺序两种播放模式
- 可调整字号（12–20 pt），长单词自动缩小字号避免被截断
- 本地 XML 词库；文件缺失或损坏时自动回退到程序集内置的同名 XML
- 支持用环境变量指定自定义 XML

## 安装

### 使用插件包

1. 把 `.cipx` 拖入 ClassIsland 的「插件」页面，或解压到：
   `ClassIsland 数据目录/data/Plugins/Englishwordsshow/`
2. 重启 ClassIsland


## 使用

1. 在 ClassIsland 主界面右键 →「组件」→ 找到「高考必背3600词」
2. 拖动到主界面上的组件行
3. 右键该组件 →「设置」，可调整轮播间隔、字号和顺序

组件不显示标题和进度，两列内容会自动垂直居中。

## 设置项

| 设置 | 默认值 | 说明 |
| --- | --- | --- |
| 轮播间隔 | 15 秒 | 每 15 秒切换一组单词，范围 3–600 秒 |
| 随机顺序 | 开启 | 关闭后按字母顺序播放，播完一轮从头开始 |
| 字体大小 | 18 pt | 英文单词字号，词性/释义按比例缩放；范围 12–20 pt |

## 词库说明

### 为什么是 3810 条？

插件名称沿用「高考必背3600词」。内置词库以高考英语 3500 词表为底本，做了以下整理：

1. 删除短语和带括号的变形提示，只保留可独立展示的单词
2. 合并同形词（如 `fall` 的名词义和动词义合并为一个词条）
3. 补齐源数据中因行错位而丢失的常用词（如 `take`、`make`、`body`、`warn`）
4. 每个词条补齐词性、中文释义（XML 中另保留音标字段，组件不显示）

整理后共 **3810 条**，是 3600 词大纲的完整超集。若需要严格 3600 条，可运行：

```bash
python tools/build_vocab.py --target 3600
```

脚本会按 ECDICT 词频舍弃部分生僻词，然后重新生成 `Assets/gaokao3600.xml`。

### XML 格式

`Assets/gaokao3600.xml`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<wordbook name="高考必背3600词" count="3810">
  <word en="abandon" pos="v." zh="放弃；舍弃；抛弃" phonetic="əˈbændən" />
  <word en="ability" pos="n." zh="能力；才干" phonetic="əˈbɪlətɪ" />
</wordbook>
```

支持的属性名（大小写不敏感）：

| 含义 | 可用属性名 |
| --- | --- |
| 英文 | `en`、`english`、`word` |
| 词性 | `pos`、`partOfSpeech`、`part_of_speech` |
| 中文释义 | `zh`、`cn`、`chinese`、`meaning` |
| 音标 | `phonetic`、`ipa`、`pronunciation` |

也可以把值写成子节点，例如 `<word><en>abandon</en>…</word>`。英文重复的词条会自动跳过。

### 自定义词库

按以下优先级查找 XML：

1. 环境变量 `ENGLISHWORDSSHOW_XML` 指向的文件
2. 插件目录 `Assets/gaokao3600.xml`
3. 插件目录 `gaokao3600.xml`
4. ClassIsland 应用目录 `Assets/gaokao3600.xml`
5. ClassIsland 应用目录 `gaokao3600.xml`
6. 程序集内置 XML（最后兜底）

因此可以直接替换插件目录下的 `Assets/gaokao3600.xml`，无需重新编译；改完重启 ClassIsland 即可。

## 从源码构建

需要 .NET 8 SDK。

```bash
dotnet build -c Release
python package_cipx.py
```

生成 `cipx/Englishwordsshow.cipx`（Windows 上 `python` 不可用时可改用 `py`）。

重新生成词库（可选，需要 Python 3.10+ 和网络）：

```bash
python tools/build_vocab.py
python tools/build_vocab.py --target 3600
```

脚本会把 qwerty-learner 的高考词表和 ECDICT 下载到 `tools/.cache/`，生成
`Assets/gaokao3600.xml`。日常构建不需要运行该脚本，XML 已随仓库提供。

## 项目结构

```
Components/                         组件与设置界面
  WordCarouselComponent.xaml        两词一屏的显示布局
  WordCarouselComponent.xaml.cs     加载、计时、渲染
  WordCarouselComponentSettings.cs  设置模型
  WordCarouselComponentSettingsControl.xaml(.cs)
Models/WordEntry.cs                 词条模型
Services/VocabularyService.cs       XML 加载与取词
Assets/gaokao3600.xml               本地词库
tools/build_vocab.py                词库生成脚本
```

## 数据来源与许可

- 代码：MIT License，见 [LICENSE](LICENSE)
- 词库整理：词条底本来自 [pluto0x0/word3500](https://github.com/pluto0x0/word3500)（MIT）的高考词表；整理释义以 3500 词表为主，词性与缺失释义由 [ECDICT](https://github.com/skywind3000/ECDICT)（MIT）校正；词条切分参考 [qwerty-learner](https://github.com/RealKai42/qwerty-learner)（GPL-3.0）中的 `GaoKao_3500.json`
- 详细版权与许可声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

词库仅用于学习用途，不构成考试大纲或出版词典的完整性保证。

