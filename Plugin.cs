using ClassIsland.Core.Abstractions;
using ClassIsland.Core.Attributes;
using ClassIsland.Core.Extensions.Registry;
using Englishwordsshow.Components;
using Englishwordsshow.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace Englishwordsshow;

[PluginEntrance]
public class Plugin : PluginBase
{
    public override void Initialize(HostBuilderContext context, IServiceCollection services)
    {
        services.AddSingleton<VocabularyService>();
        services.AddComponent<WordCarouselComponent, WordCarouselComponentSettingsControl>();
    }
}
