using System.Xml.Linq;
using Englishwordsshow.Models;

namespace Englishwordsshow.Services;

/// <summary>
/// 本地词库服务：从插件目录下的 XML（或内置资源）加载词条，并按顺序/随机顺序取词。
/// 不进行任何网络请求。
/// </summary>
public sealed class VocabularyService
{
    private const string DataFileName = "gaokao3600.xml";

    private readonly List<WordEntry> _words = new();
    private readonly Random _random = new();

    private int[] _order = Array.Empty<int>();
    private int _position;
    private bool _shuffled;
    private bool _orderInitialized;

    /// <summary>是否已成功加载词库。</summary>
    public bool IsLoaded => _words.Count > 0;

    /// <summary>词条总数。</summary>
    public int Count => _words.Count;

    /// <summary>最近一次加载失败的详细信息。</summary>
    public string? LastError { get; private set; }

    /// <summary>实际使用的 XML 来源（文件路径或“内置资源”）。</summary>
    public string? Source { get; private set; }

    /// <summary>已加载的外部文件解析警告（成功回退到内置资源时可能有值）。</summary>
    public string? Diagnostics { get; private set; }

    /// <summary>上一次取词时第一个词在词库中的序号（从 1 开始）。</summary>
    public int LastPairStart { get; private set; }

    /// <summary>上一次取词时最后一个词的序号（从 1 开始）。</summary>
    public int LastPairEnd { get; private set; }

    /// <summary>
    /// 加载本地 XML。依次尝试环境变量、插件目录、应用目录中的 XML，最后回退到内置资源。
    /// </summary>
    public bool Load()
    {
        _words.Clear();
        _order = Array.Empty<int>();
        _position = 0;
        _orderInitialized = false;
        LastError = null;
        Diagnostics = null;
        Source = null;

        var errors = new List<string>();

        foreach (var path in GetCandidatePaths())
        {
            if (!File.Exists(path))
                continue;

            if (TryLoadFromFile(path, out var error))
            {
                Source = path;
                ResetOrder();
                return true;
            }

            errors.Add($"{path}：{error}");
        }

        if (TryLoadFromEmbedded(out var embeddedError))
        {
            Source = "内置资源 " + DataFileName;
            Diagnostics = errors.Count > 0 ? string.Join(Environment.NewLine, errors) : null;
            ResetOrder();
            return true;
        }

        if (!string.IsNullOrWhiteSpace(embeddedError))
            errors.Add($"内置资源：{embeddedError}");

        LastError = errors.Count > 0
            ? string.Join(Environment.NewLine, errors)
            : $"未找到本地词库文件 {DataFileName}。";
        return false;
    }

    /// <summary>
    /// 重置取词顺序。下次取词时按新的模式重新生成。
    /// </summary>
    public void ResetOrder()
    {
        _order = Array.Empty<int>();
        _position = 0;
        _orderInitialized = false;
    }

    /// <summary>
    /// 取下一组词。顺序模式播完一轮后从头开始；随机模式每轮重新打乱。
    /// </summary>
    public IReadOnlyList<WordEntry> NextPair(int count = 2, bool shuffle = true)
    {
        if (_words.Count == 0)
            return Array.Empty<WordEntry>();

        var take = Math.Clamp(count, 1, _words.Count);
        EnsureOrder(shuffle);

        if (_position + take > _order.Length)
        {
            // 一轮结束：顺序模式回到开头；随机模式重新洗牌。
            BuildOrder(shuffle, avoidFirst: _order.Length > 0 ? _order[^1] : -1);
            _position = 0;
        }

        var result = new WordEntry[take];
        for (var i = 0; i < take; i++)
            result[i] = _words[_order[_position + i]];

        LastPairStart = _position + 1;
        LastPairEnd = _position + take;
        _position += take;
        return result;
    }

    private void EnsureOrder(bool shuffle)
    {
        if (_orderInitialized && _order.Length == _words.Count && _shuffled == shuffle)
            return;

        BuildOrder(shuffle, avoidFirst: -1);
        _position = 0;
    }

    private void BuildOrder(bool shuffle, int avoidFirst)
    {
        _order = Enumerable.Range(0, _words.Count).ToArray();
        _shuffled = shuffle;
        _orderInitialized = true;

        if (!shuffle)
            return;

        for (var i = _order.Length - 1; i > 0; i--)
        {
            var j = _random.Next(i + 1);
            (_order[i], _order[j]) = (_order[j], _order[i]);
        }

        if (avoidFirst >= 0 && _order.Length > 2 && _order[0] == avoidFirst)
        {
            var swap = _random.Next(1, _order.Length);
            (_order[0], _order[swap]) = (_order[swap], _order[0]);
        }
    }

    private static IEnumerable<string> GetCandidatePaths()
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        var configured = Environment.GetEnvironmentVariable("ENGLISHWORDSSHOW_XML");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            var full = Path.GetFullPath(configured);
            if (seen.Add(full))
                yield return full;
        }

        var roots = new List<string>();
        var assemblyDir = Path.GetDirectoryName(typeof(VocabularyService).Assembly.Location);
        if (!string.IsNullOrWhiteSpace(assemblyDir))
            roots.Add(assemblyDir);
        roots.Add(AppContext.BaseDirectory);

        foreach (var root in roots)
        {
            foreach (var candidate in new[]
                     {
                         Path.Combine(root, "Assets", DataFileName),
                         Path.Combine(root, DataFileName),
                     })
            {
                if (seen.Add(candidate))
                    yield return candidate;
            }
        }
    }

    private bool TryLoadFromFile(string path, out string? error)
    {
        try
        {
            using var stream = File.OpenRead(path);
            return TryParse(stream, path, out error);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            error = $"无法读取文件：{ex.Message}";
            return false;
        }
    }

    private bool TryLoadFromEmbedded(out string? error)
    {
        try
        {
            var assembly = typeof(VocabularyService).Assembly;
            var resource = assembly.GetManifestResourceNames()
                .FirstOrDefault(name => name.EndsWith(DataFileName, StringComparison.OrdinalIgnoreCase));

            if (resource is null)
            {
                error = $"程序集中未找到 {DataFileName}";
                return false;
            }

            using var stream = assembly.GetManifestResourceStream(resource);
            if (stream is null)
            {
                error = "无法打开内置资源流";
                return false;
            }

            return TryParse(stream, resource, out error);
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }

    private bool TryParse(Stream stream, string source, out string? error)
    {
        try
        {
            var document = XDocument.Load(stream);
            var root = document.Root;
            if (root is null)
            {
                error = "XML 没有根节点";
                return false;
            }

            var parsed = new List<WordEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var element in root.Elements())
            {
                if (!string.Equals(element.Name.LocalName, "word", StringComparison.OrdinalIgnoreCase))
                    continue;

                var english = Attribute(element, "en", "english", "word");
                var chinese = Attribute(element, "zh", "cn", "chinese", "meaning");
                if (string.IsNullOrWhiteSpace(english) || string.IsNullOrWhiteSpace(chinese))
                    continue;

                if (!seen.Add(english))
                    continue;

                parsed.Add(new WordEntry
                {
                    English = english,
                    PartOfSpeech = Attribute(element, "pos", "partOfSpeech", "part_of_speech"),
                    Chinese = chinese,
                    Phonetic = Attribute(element, "phonetic", "ipa", "pronunciation"),
                });
            }

            if (parsed.Count == 0)
            {
                error = "XML 中没有可用的 word 节点";
                return false;
            }

            _words.AddRange(parsed);
            error = null;
            return true;
        }
        catch (Exception ex) when (ex is System.Xml.XmlException or IOException)
        {
            error = $"XML 解析失败：{ex.Message}";
            return false;
        }
    }

    private static string Attribute(XElement element, params string[] names)
    {
        foreach (var attribute in element.Attributes())
        {
            if (names.Any(name => string.Equals(attribute.Name.LocalName, name, StringComparison.OrdinalIgnoreCase)))
                return attribute.Value.Trim();
        }

        foreach (var name in names)
        {
            var child = element.Elements()
                .FirstOrDefault(e => string.Equals(e.Name.LocalName, name, StringComparison.OrdinalIgnoreCase));
            if (child is not null)
                return child.Value.Trim();
        }

        return "";
    }
}
