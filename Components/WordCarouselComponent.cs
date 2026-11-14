using System.ComponentModel;
using Avalonia.Interactivity;
using Avalonia.Threading;
using ClassIsland.Core.Abstractions.Controls;
using ClassIsland.Core.Attributes;
using Englishwordsshow.Models;
using Englishwordsshow.Services;

namespace Englishwordsshow.Components;

/// <summary>
/// 高考必背 3600 词轮播组件：每次显示两个单词（英文 + 词性/中文释义）。
/// </summary>
[ComponentInfo(
    "4f8a1c2e-9b3d-4a6f-8e21-7c5d0b9a3f14",
    "高考必背3600词",
    "每次显示 2 个高考英语单词，包含英文、词性和中文释义")]
public partial class WordCarouselComponent : ComponentBase<WordCarouselComponentSettings>
{
    private readonly VocabularyService _vocabulary;
    private System.Timers.Timer? _timer;
    private IReadOnlyList<WordEntry> _current = Array.Empty<WordEntry>();
    private bool _loaded;
    private bool _subscribed;

    public WordCarouselComponent() : this(new VocabularyService())
    {
    }

    public WordCarouselComponent(VocabularyService vocabulary)
    {
        _vocabulary = vocabulary;
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        SizeChanged += (_, _) => UpdateColumnWidths();
    }

    private void OnLoaded(object? sender, RoutedEventArgs e)
    {
        if (!_loaded)
            _loaded = _vocabulary.Load();

        if (!_subscribed && Settings is not null)
        {
            Settings.PropertyChanged += OnSettingsPropertyChanged;
            _subscribed = true;
        }

        if (_loaded)
        {
            if (_current.Count == 0)
                ShowNextPair();
            else
                RenderPair(_current);
        }
        else
        {
            RenderError(_vocabulary.LastError);
        }

        UpdateColumnWidths();
        Dispatcher.UIThread.Post(UpdateColumnWidths);
        StartTimer();
    }

    /// <summary>
    /// 组件宽度由 ClassIsland 的组件行决定。给文字块设置明确宽度，避免
    /// TextBlock 按无限宽度测量后超出组件边界，导致汉译被横向裁掉。
    /// </summary>
    private void UpdateColumnWidths()
    {
        var width = Bounds.Width;
        if (width <= 1)
            return;

        var column = Math.Max(40, (width - 20) / 2);
        Word1Text.Width = column;
        Detail1Text.Width = column;
        Word2Text.Width = column;
        Detail2Text.Width = column;
    }

    private void OnUnloaded(object? sender, RoutedEventArgs e)
    {
        StopTimer();

        if (_subscribed && Settings is not null)
        {
            Settings.PropertyChanged -= OnSettingsPropertyChanged;
            _subscribed = false;
        }
    }

    private void OnSettingsPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        switch (e.PropertyName)
        {
            case nameof(WordCarouselComponentSettings.IntervalSeconds):
                Dispatcher.UIThread.Post(StartTimer);
                break;
            case nameof(WordCarouselComponentSettings.RandomOrder):
                Dispatcher.UIThread.Post(() =>
                {
                    _vocabulary.ResetOrder();
                    ShowNextPair();
                });
                break;
            default:
                Dispatcher.UIThread.Post(() => RenderPair(_current));
                break;
        }
    }

    private void StartTimer()
    {
        StopTimer();

        var seconds = Math.Clamp(Settings?.IntervalSeconds ?? 15, 3, 600);
        _timer = new System.Timers.Timer(seconds * 1000.0)
        {
            AutoReset = true,
        };
        _timer.Elapsed += OnTimerElapsed;
        _timer.Start();
    }

    private void StopTimer()
    {
        if (_timer is null)
            return;

        _timer.Stop();
        _timer.Elapsed -= OnTimerElapsed;
        _timer.Dispose();
        _timer = null;
    }

    private void OnTimerElapsed(object? sender, System.Timers.ElapsedEventArgs e)
    {
        Dispatcher.UIThread.Post(() =>
        {
            if (_loaded)
                ShowNextPair();
        });
    }

    private void ShowNextPair()
    {
        if (!_vocabulary.IsLoaded)
            return;

        _current = _vocabulary.NextPair(2, Settings?.RandomOrder ?? true);
        RenderPair(_current);
    }

    private void RenderPair(IReadOnlyList<WordEntry> pair)
    {
        if (pair.Count == 0)
        {
            RenderError(_vocabulary.LastError);
            return;
        }

        var size = Settings?.FontSize ?? 18;
        ApplyCard(pair[0], Word1Text, Detail1Text, size);

        if (pair.Count > 1)
        {
            ApplyCard(pair[1], Word2Text, Detail2Text, size);
        }
        else
        {
            Word2Text.Text = "";
            EnsureInlines(Detail2Text).Clear();
        }
    }

    private static void ApplyCard(WordEntry entry, Avalonia.Controls.TextBlock word, Avalonia.Controls.TextBlock detail, double size)
    {
        word.Text = entry.English;
        word.FontSize = size * WordScale(entry.English);

        var inlines = EnsureInlines(detail);
        inlines.Clear();
        var partOfSpeech = string.IsNullOrWhiteSpace(entry.PartOfSpeech) ? "" : entry.PartOfSpeech.Trim();
        if (partOfSpeech.Length > 0)
        {
            inlines.Add(new Avalonia.Controls.Documents.Run
            {
                Text = partOfSpeech + "  ",
                Foreground = Avalonia.Media.Brushes.DodgerBlue,
                FontWeight = Avalonia.Media.FontWeight.SemiBold,
            });
        }

        inlines.Add(new Avalonia.Controls.Documents.Run { Text = entry.Chinese });
        detail.FontSize = Math.Max(10, size * 0.55);
        detail.LineHeight = Math.Max(12, size * 0.66);
    }

    private static Avalonia.Controls.Documents.InlineCollection EnsureInlines(Avalonia.Controls.TextBlock block)
        => block.Inlines ??= new Avalonia.Controls.Documents.InlineCollection();

    private static double WordScale(string english)
        => english.Length switch
        {
            <= 9 => 1.0,
            <= 11 => 0.90,
            <= 13 => 0.80,
            <= 16 => 0.70,
            _ => 0.60,
        };

    private void RenderError(string? message)
    {
        var size = Settings?.FontSize ?? 18;

        Word1Text.Text = "词库加载失败";
        Word1Text.FontSize = size * 0.8;
        var inlines = EnsureInlines(Detail1Text);
        inlines.Clear();
        inlines.Add(new Avalonia.Controls.Documents.Run
        {
            Text = message ?? "未找到 gaokao3600.xml",
        });
        Detail1Text.FontSize = Math.Max(9, size * 0.5);
        Detail1Text.LineHeight = Math.Max(12, size * 0.65);

        Word2Text.Text = "";
        EnsureInlines(Detail2Text).Clear();
    }
}
