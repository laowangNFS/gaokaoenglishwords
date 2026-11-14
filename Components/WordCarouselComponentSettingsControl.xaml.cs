using Avalonia.Interactivity;
using ClassIsland.Core.Abstractions.Controls;

namespace Englishwordsshow.Components;

public partial class WordCarouselComponentSettingsControl : ComponentBase<WordCarouselComponentSettings>
{
    public WordCarouselComponentSettingsControl()
    {
        InitializeComponent();
        DataContext = this;
        Loaded += OnLoaded;
    }

    private void OnLoaded(object? sender, RoutedEventArgs e)
    {
        DataContext = this;
    }
}
