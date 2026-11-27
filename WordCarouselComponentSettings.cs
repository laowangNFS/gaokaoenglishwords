using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace Englishwordsshow.Components;

/// <summary>
/// 组件设置：轮播间隔、字体大小与播放顺序。
/// </summary>
public class WordCarouselComponentSettings : INotifyPropertyChanged
{
    private int _intervalSeconds = 15;
    private double _fontSize = 18;
    private bool _randomOrder = true;

    /// <summary>轮播间隔（秒）。</summary>
    public int IntervalSeconds
    {
        get => _intervalSeconds;
        set
        {
            var clamped = Math.Clamp(value, 3, 600);
            if (_intervalSeconds == clamped) return;
            _intervalSeconds = clamped;
            OnPropertyChanged();
        }
    }

    /// <summary>英文单词字号（词性/中文释义按比例缩放）。</summary>
    public double FontSize
    {
        get => _fontSize;
        set
        {
            // 组件内容高度只有约 55px，字号过大会把中文释义挤出可视区域。
            var clamped = Math.Clamp(value, 14, 22);
            if (Math.Abs(_fontSize - clamped) < 0.01) return;
            _fontSize = clamped;
            OnPropertyChanged();
        }
    }

    /// <summary>true：每轮随机打乱；false：按字母顺序轮播。</summary>
    public bool RandomOrder
    {
        get => _randomOrder;
        set
        {
            if (_randomOrder == value) return;
            _randomOrder = value;
            OnPropertyChanged();
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
}
