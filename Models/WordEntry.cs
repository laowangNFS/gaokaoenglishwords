namespace Englishwordsshow.Models;

/// <summary>
/// 一个词条：英文、词性、中文释义、音标。
/// </summary>
public sealed class WordEntry
{
    public string English { get; init; } = "";

    public string PartOfSpeech { get; init; } = "";

    public string Chinese { get; init; } = "";

    public string Phonetic { get; init; } = "";
}
