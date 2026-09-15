import React, { useState, useEffect } from 'react';

interface ProviderInfo {
  name: string;
  display_name?: string;
  capabilities: { text: boolean; image: boolean; video: boolean };
}

interface Settings {
  default_llm_provider: string;
  default_image_provider: string;
  default_video_provider: string;
  ollama_api_url: string;
  ollama_model: string;
  openai_api_url: string;
  openai_model: string;
  openai_image_model: string;
  openai_compat_name: string;
  openai_compat_api_url: string;
  openai_compat_model: string;
  openai_compat_auth_header: string;
  openai_compat_auth_scheme: string;
  openai_compat_max_tokens_param: string;
  openai_compat_max_tokens: number;
  openai_compat_temperature: number;
  openai_compat_top_p: number;
  openai_compat_timeout: number;
  dashscope_api_url: string;
  dashscope_image_model: string;
  dashscope_image_size: string;
  dashscope_use_async: boolean;
  dashscope_prompt_extend: boolean;
  dashscope_prompt_extend_mode: string;
  dashscope_enable_thinking: boolean;
  dashscope_watermark: boolean;
  comfyui_api_url: string;
  wan3_api_url: string;
  wan3_model: string;
  wan3_resolution: string;
  wan3_ratio: string;
  wan3_duration: number;
  wan3_audio: boolean;
  wan3_seed: number;
  wan3_prompt_extend: boolean;
  wan3_watermark: boolean;
  wan3_poll_interval: number;
  wan3_timeout: number;
  asset_dir: string;
  ffmpeg_path: string;
}

interface Props {
  onClose: () => void;
}

export default function SettingsPanel({ onClose }: Props) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<string>('');

  // Form state
  const [llmProvider, setLlmProvider] = useState('mock');
  const [imageProvider, setImageProvider] = useState('mock');
  const [videoProvider, setVideoProvider] = useState('mock');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [ollamaModel, setOllamaModel] = useState('llama3.2');
  const [openaiKey, setOpenaiKey] = useState('');
  const [openaiUrl, setOpenaiUrl] = useState('https://api.openai.com/v1');
  const [openaiModel, setOpenaiModel] = useState('gpt-4');
  const [compatName, setCompatName] = useState('Xiaomi MiMo');
  const [compatUrl, setCompatUrl] = useState('https://api.xiaomimimo.com/v1');
  const [compatKey, setCompatKey] = useState('');
  const [compatModel, setCompatModel] = useState('mimo-v2.5-pro');
  const [compatAuthHeader, setCompatAuthHeader] = useState('api-key');
  const [compatAuthScheme, setCompatAuthScheme] = useState('');
  const [compatMaxTokensParam, setCompatMaxTokensParam] = useState('max_completion_tokens');
  const [compatMaxTokens, setCompatMaxTokens] = useState(4096);
  const [compatTemperature, setCompatTemperature] = useState(1.0);
  const [compatTopP, setCompatTopP] = useState(0.95);
  const [compatTimeout, setCompatTimeout] = useState(120);
  const [comfyuiUrl, setComfyuiUrl] = useState('http://localhost:8188');
  const [dashscopeUrl, setDashscopeUrl] = useState('https://dashscope.aliyuncs.com/api/v1');
  const [dashscopeKey, setDashscopeKey] = useState('');
  const [dashscopeImageModel, setDashscopeImageModel] = useState('qwen-image-3.0');
  const [dashscopeImageSize, setDashscopeImageSize] = useState('1280x720');
  const [dashscopeUseAsync, setDashscopeUseAsync] = useState(false);
  const [dashscopePromptExtend, setDashscopePromptExtend] = useState(true);
  const [dashscopePromptExtendMode, setDashscopePromptExtendMode] = useState('direct');
  const [dashscopeEnableThinking, setDashscopeEnableThinking] = useState(true);
  const [dashscopeWatermark, setDashscopeWatermark] = useState(false);
  const [wan3Url, setWan3Url] = useState('https://dashscope.aliyuncs.com/api/v1');
  const [wan3Key, setWan3Key] = useState('');
  const [wan3Model, setWan3Model] = useState('wan3.0-video');
  const [wan3Resolution, setWan3Resolution] = useState('480P');
  const [wan3Ratio, setWan3Ratio] = useState('adaptive');
  const [wan3Duration, setWan3Duration] = useState(5);
  const [wan3Audio, setWan3Audio] = useState(true);
  const [wan3Seed, setWan3Seed] = useState(-1);
  const [wan3PromptExtend, setWan3PromptExtend] = useState(true);
  const [wan3Watermark, setWan3Watermark] = useState(false);
  const [wan3PollInterval, setWan3PollInterval] = useState(5);
  const [wan3Timeout, setWan3Timeout] = useState(1800);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [provRes, settingsRes] = await Promise.all([
        fetch('/api/config/providers'),
        fetch('/api/config/settings'),
      ]);
      if (provRes.ok) setProviders(await provRes.json());
      if (settingsRes.ok) {
        const s = await settingsRes.json();
        setSettings(s);
        setLlmProvider(s.default_llm_provider);
        setImageProvider(s.default_image_provider);
        setVideoProvider(s.default_video_provider);
        setOllamaUrl(s.ollama_api_url);
        setOllamaModel(s.ollama_model);
        setOpenaiUrl(s.openai_api_url);
        setOpenaiModel(s.openai_model);
        setCompatName(s.openai_compat_name);
        setCompatUrl(s.openai_compat_api_url);
        setCompatModel(s.openai_compat_model);
        setCompatAuthHeader(s.openai_compat_auth_header);
        setCompatAuthScheme(s.openai_compat_auth_scheme);
        setCompatMaxTokensParam(s.openai_compat_max_tokens_param);
        setCompatMaxTokens(s.openai_compat_max_tokens);
        setCompatTemperature(s.openai_compat_temperature);
        setCompatTopP(s.openai_compat_top_p);
        setCompatTimeout(s.openai_compat_timeout);
        setComfyuiUrl(s.comfyui_api_url);
        setDashscopeUrl(s.dashscope_api_url);
        setDashscopeImageModel(s.dashscope_image_model);
        setDashscopeImageSize(s.dashscope_image_size);
        setDashscopeUseAsync(s.dashscope_use_async);
        setDashscopePromptExtend(s.dashscope_prompt_extend);
        setDashscopePromptExtendMode(s.dashscope_prompt_extend_mode);
        setDashscopeEnableThinking(s.dashscope_enable_thinking);
        setDashscopeWatermark(s.dashscope_watermark);
        setWan3Url(s.wan3_api_url);
        setWan3Model(s.wan3_model);
        setWan3Resolution(s.wan3_resolution);
        setWan3Ratio(s.wan3_ratio);
        setWan3Duration(s.wan3_duration);
        setWan3Audio(s.wan3_audio);
        setWan3Seed(s.wan3_seed);
        setWan3PromptExtend(s.wan3_prompt_extend);
        setWan3Watermark(s.wan3_watermark);
        setWan3PollInterval(s.wan3_poll_interval);
        setWan3Timeout(s.wan3_timeout);
      }
    } catch (e) {
      console.error('Failed to load settings', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const resp = await fetch('/api/config/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_llm_provider: llmProvider,
          default_image_provider: imageProvider,
          default_video_provider: videoProvider,
          ollama_api_url: ollamaUrl,
          ollama_model: ollamaModel,
          openai_api_key: openaiKey || undefined,
          openai_api_url: openaiUrl,
          openai_model: openaiModel,
          openai_compat_name: compatName,
          openai_compat_api_url: compatUrl,
          openai_compat_api_key: compatKey || undefined,
          openai_compat_model: compatModel,
          openai_compat_auth_header: compatAuthHeader,
          openai_compat_auth_scheme: compatAuthScheme,
          openai_compat_max_tokens_param: compatMaxTokensParam,
          openai_compat_max_tokens: compatMaxTokens,
          openai_compat_temperature: compatTemperature,
          openai_compat_top_p: compatTopP,
          openai_compat_timeout: compatTimeout,
          comfyui_api_url: comfyuiUrl,
          dashscope_api_url: dashscopeUrl,
          dashscope_api_key: dashscopeKey || undefined,
          dashscope_image_model: dashscopeImageModel,
          dashscope_image_size: dashscopeImageSize,
          dashscope_use_async: dashscopeUseAsync,
          dashscope_prompt_extend: dashscopePromptExtend,
          dashscope_prompt_extend_mode: dashscopePromptExtendMode,
          dashscope_enable_thinking: dashscopeEnableThinking,
          dashscope_watermark: dashscopeWatermark,
          wan3_api_url: wan3Url,
          wan3_api_key: wan3Key || undefined,
          wan3_model: wan3Model,
          wan3_resolution: wan3Resolution,
          wan3_ratio: wan3Ratio,
          wan3_duration: wan3Duration,
          wan3_audio: wan3Audio,
          wan3_seed: wan3Seed,
          wan3_prompt_extend: wan3PromptExtend,
          wan3_watermark: wan3Watermark,
          wan3_poll_interval: wan3PollInterval,
          wan3_timeout: wan3Timeout,
        }),
      });
      if (resp.ok) {
        setTestResult('✅ 设置已保存');
        setTimeout(() => setTestResult(''), 3000);
      }
    } catch (e) {
      setTestResult('❌ 保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTestProvider = async (name: string) => {
    setTestResult(`⏳ 测试 ${name}...`);
    try {
      const resp = await fetch('/api/config/test-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_name: name }),
      });
      const data = await resp.json();
      setTestResult(data.healthy ? `✅ ${name} 连接正常` : `❌ ${name} 连接失败`);
    } catch {
      setTestResult(`❌ ${name} 测试失败`);
    }
  };

  if (loading) {
    return (
      <div style={styles.overlay}>
        <div style={styles.panel}>
          <div style={styles.loading}>加载中...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>⚙️ 设置</h2>
          <button style={styles.closeBtn} onClick={onClose}>×</button>
        </div>

        <div style={styles.content}>
          {/* Provider Selection */}
          <section style={styles.section}>
            <h3 style={styles.sectionTitle}>🤖 Provider 选择</h3>

            <label style={styles.label}>文本生成 (LLM)</label>
            <select style={styles.select} value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)}>
              <option value="mock">Mock (测试)</option>
              <option value="ollama">Ollama (本地)</option>
              <option value="openai">OpenAI</option>
              <option value="openai_compat">自定义 OpenAI-compatible（MiMo）</option>
            </select>

            <label style={styles.label}>图像生成</label>
            <select style={styles.select} value={imageProvider} onChange={(e) => setImageProvider(e.target.value)}>
              <option value="mock">Mock (测试)</option>
              <option value="comfyui">ComfyUI</option>
              <option value="wan3">万相 3.0（百炼）</option>
              <option value="openai">OpenAI (DALL-E)</option>
              <option value="dashscope">DashScope (Qwen Image)</option>
            </select>

            <label style={styles.label}>视频生成</label>
            <select style={styles.select} value={videoProvider} onChange={(e) => setVideoProvider(e.target.value)}>
              <option value="mock">Mock (测试)</option>
              <option value="comfyui">ComfyUI</option>
            </select>
          </section>

          {/* Ollama Config */}
          {llmProvider === 'ollama' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>🦙 Ollama 配置</h3>
              <label style={styles.label}>API URL</label>
              <input style={styles.input} value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
              <label style={styles.label}>模型</label>
              <input style={styles.input} value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('ollama')}>测试连接</button>
            </section>
          )}

          {/* OpenAI Config */}
          {llmProvider === 'openai' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>🤖 OpenAI 配置</h3>
              <label style={styles.label}>API Key</label>
              <input style={styles.input} type="password" placeholder="sk-..." value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)} />
              <label style={styles.label}>API Base URL</label>
              <input style={styles.input} value={openaiUrl} onChange={(e) => setOpenaiUrl(e.target.value)} />
              <label style={styles.label}>文本模型</label>
              <input style={styles.input} value={openaiModel} onChange={(e) => setOpenaiModel(e.target.value)} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('openai')}>测试连接</button>
            </section>
          )}

          {llmProvider === 'openai_compat' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>自定义 OpenAI-compatible LLM</h3>
              <label style={styles.label}>配置名称</label>
              <input style={styles.input} value={compatName} onChange={(e) => setCompatName(e.target.value)} />
              <label style={styles.label}>API Base URL</label>
              <input style={styles.input} value={compatUrl} onChange={(e) => setCompatUrl(e.target.value)} />
              <label style={styles.label}>API Key</label>
              <input style={styles.input} type="password" placeholder="sk-... / tp-..." value={compatKey} onChange={(e) => setCompatKey(e.target.value)} />
              <label style={styles.label}>模型</label>
              <input style={styles.input} value={compatModel} onChange={(e) => setCompatModel(e.target.value)} />
              <label style={styles.label}>认证 Header</label>
              <input style={styles.input} value={compatAuthHeader} onChange={(e) => setCompatAuthHeader(e.target.value)} />
              <label style={styles.label}>认证前缀（MiMo 留空，常规 OpenAI 填 Bearer）</label>
              <input style={styles.input} value={compatAuthScheme} onChange={(e) => setCompatAuthScheme(e.target.value)} />
              <label style={styles.label}>Token 参数名</label>
              <select style={styles.select} value={compatMaxTokensParam} onChange={(e) => setCompatMaxTokensParam(e.target.value)}>
                <option value="max_completion_tokens">max_completion_tokens</option>
                <option value="max_tokens">max_tokens</option>
              </select>
              <label style={styles.label}>最大输出 Tokens</label>
              <input style={styles.input} type="number" min={1} value={compatMaxTokens} onChange={(e) => setCompatMaxTokens(Number(e.target.value))} />
              <label style={styles.label}>Temperature</label>
              <input style={styles.input} type="number" min={0} max={2} step={0.1} value={compatTemperature} onChange={(e) => setCompatTemperature(Number(e.target.value))} />
              <label style={styles.label}>Top P</label>
              <input style={styles.input} type="number" min={0.01} max={1} step={0.05} value={compatTopP} onChange={(e) => setCompatTopP(Number(e.target.value))} />
              <label style={styles.label}>超时（秒）</label>
              <input style={styles.input} type="number" min={1} max={1800} value={compatTimeout} onChange={(e) => setCompatTimeout(Number(e.target.value))} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('openai_compat')}>测试连接</button>
            </section>
          )}

          {/* ComfyUI Config */}
          {imageProvider === 'comfyui' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>🎨 ComfyUI 配置</h3>
              <label style={styles.label}>API URL</label>
              <input style={styles.input} value={comfyuiUrl} onChange={(e) => setComfyuiUrl(e.target.value)} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('comfyui')}>测试连接</button>
            </section>
          )}

          {videoProvider === 'comfyui' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>ComfyUI 视频配置</h3>
              <label style={styles.label}>API URL</label>
              <input style={styles.input} value={comfyuiUrl} onChange={(e) => setComfyuiUrl(e.target.value)} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('comfyui')}>测试连接</button>
            </section>
          )}

          {videoProvider === 'wan3' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>万相 3.0 视频配置</h3>
              <label style={styles.label}>API Base URL</label>
              <input style={styles.input} value={wan3Url} onChange={(e) => setWan3Url(e.target.value)} />
              <label style={styles.label}>API Key（留空则沿用 DashScope Key）</label>
              <input style={styles.input} type="password" value={wan3Key} onChange={(e) => setWan3Key(e.target.value)} />
              <label style={styles.label}>模型</label>
              <select style={styles.select} value={wan3Model} onChange={(e) => setWan3Model(e.target.value)}>
                <option value="wan3.0-video">wan3.0-video（标准版）</option>
                <option value="wan3.0-video-prime">wan3.0-video-prime（高速版）</option>
              </select>
              <label style={styles.label}>分辨率</label>
              <select style={styles.select} value={wan3Resolution} onChange={(e) => setWan3Resolution(e.target.value)}>
                <option value="480P">480P（默认）</option>
                <option value="720P">720P</option>
                <option value="1080P">1080P</option>
              </select>
              <label style={styles.label}>宽高比</label>
              <select style={styles.select} value={wan3Ratio} onChange={(e) => setWan3Ratio(e.target.value)}>
                {['adaptive', '16:9', '4:3', '1:1', '3:4', '9:16'].map((ratio) => <option key={ratio} value={ratio}>{ratio}</option>)}
              </select>
              <label style={styles.label}>时长（-1 智能，或 2-30 秒）</label>
              <input style={styles.input} type="number" min={-1} max={30} value={wan3Duration} onChange={(e) => setWan3Duration(Number(e.target.value))} />
              <label style={styles.label}>随机种子（-1 随机）</label>
              <input style={styles.input} type="number" min={-1} max={2147483647} value={wan3Seed} onChange={(e) => setWan3Seed(Number(e.target.value))} />
              <label style={styles.checkboxLabel}><input type="checkbox" checked={wan3Audio} onChange={(e) => setWan3Audio(e.target.checked)} />生成音轨</label>
              <label style={styles.checkboxLabel}><input type="checkbox" checked={wan3PromptExtend} onChange={(e) => setWan3PromptExtend(e.target.checked)} />提示词智能改写</label>
              <label style={styles.checkboxLabel}><input type="checkbox" checked={wan3Watermark} onChange={(e) => setWan3Watermark(e.target.checked)} />添加模型水印</label>
              <label style={styles.label}>轮询间隔（秒）</label>
              <input style={styles.input} type="number" min={1} value={wan3PollInterval} onChange={(e) => setWan3PollInterval(Number(e.target.value))} />
              <label style={styles.label}>任务超时（秒）</label>
              <input style={styles.input} type="number" min={60} value={wan3Timeout} onChange={(e) => setWan3Timeout(Number(e.target.value))} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('wan3')}>测试 Key 与端点</button>
            </section>
          )}

          {imageProvider === 'dashscope' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>Qwen Image 配置</h3>
              <label style={styles.label}>API Base URL</label>
              <input style={styles.input} value={dashscopeUrl} onChange={(e) => setDashscopeUrl(e.target.value)} />
              <label style={styles.label}>API Key（留空则沿用已配置的 Key）</label>
              <input style={styles.input} type="password" value={dashscopeKey} onChange={(e) => setDashscopeKey(e.target.value)} />
              <label style={styles.label}>图像模型</label>
              <input style={styles.input} value={dashscopeImageModel} onChange={(e) => setDashscopeImageModel(e.target.value)} />
              <label style={styles.label}>图像尺寸</label>
              <input style={styles.input} value={dashscopeImageSize} onChange={(e) => setDashscopeImageSize(e.target.value)} />
              <label style={styles.checkboxLabel}><input type="checkbox" checked={dashscopeUseAsync} onChange={(e) => setDashscopeUseAsync(e.target.checked)} />批量任务使用异步接口</label>
              <label style={styles.checkboxLabel}><input type="checkbox" checked={dashscopePromptExtend} onChange={(e) => setDashscopePromptExtend(e.target.checked)} />提示词智能改写</label>
              <label style={styles.label}>提示词改写方式</label>
              <select style={styles.select} value={dashscopePromptExtendMode} onChange={(e) => setDashscopePromptExtendMode(e.target.value)}>
                <option value="direct">direct（通用）</option>
                <option value="agent">agent（仅文生图）</option>
              </select>
              <label style={styles.checkboxLabel}><input type="checkbox" checked={dashscopeEnableThinking} onChange={(e) => setDashscopeEnableThinking(e.target.checked)} />开启思考模式</label>
              <label style={styles.checkboxLabel}><input type="checkbox" checked={dashscopeWatermark} onChange={(e) => setDashscopeWatermark(e.target.checked)} />添加模型水印</label>
              <button style={styles.testBtn} onClick={() => handleTestProvider('dashscope')}>测试连接</button>
            </section>
          )}

          {/* Registered Providers */}
          <section style={styles.section}>
            <h3 style={styles.sectionTitle}>📋 已注册 Provider</h3>
            {providers.map((p) => (
              <div key={p.name} style={styles.providerCard}>
                <strong>{p.display_name || p.name}</strong>
                <span style={styles.capabilities}>
                  {p.capabilities.text && '📝 '}
                  {p.capabilities.image && '🖼️ '}
                  {p.capabilities.video && '🎬 '}
                </span>
              </div>
            ))}
          </section>
        </div>

        {/* Footer */}
        <div style={styles.footer}>
          {testResult && <span style={styles.testResult}>{testResult}</span>}
          <button style={styles.saveBtn} onClick={handleSave} disabled={saving}>
            {saving ? '保存中...' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', zIndex: 1000,
  },
  panel: {
    background: '#1e1e2e', borderRadius: 12, width: 480, maxHeight: '80vh',
    display: 'flex', flexDirection: 'column', border: '1px solid #444',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid #333',
  },
  title: { margin: 0, fontSize: 18, color: '#e0e0e0' },
  closeBtn: {
    background: 'none', border: 'none', color: '#888', fontSize: 24, cursor: 'pointer',
  },
  content: { flex: 1, overflow: 'auto', padding: 20 },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 14, color: '#aaa', marginBottom: 8 },
  label: { display: 'block', fontSize: 12, color: '#888', marginBottom: 4, marginTop: 8 },
  checkboxLabel: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#aaa', marginTop: 10 },
  select: {
    width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #444',
    background: '#2a2a3a', color: '#e0e0e0', fontSize: 14,
  },
  input: {
    width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #444',
    background: '#2a2a3a', color: '#e0e0e0', fontSize: 14, boxSizing: 'border-box',
  },
  testBtn: {
    marginTop: 8, padding: '6px 12px', borderRadius: 6, border: '1px solid #555',
    background: '#333', color: '#aaa', cursor: 'pointer', fontSize: 12,
  },
  providerCard: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px', borderRadius: 6, background: '#2a2a3a', marginBottom: 4,
    color: '#e0e0e0', fontSize: 13,
  },
  capabilities: { fontSize: 14 },
  footer: {
    display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12,
    padding: '12px 20px', borderTop: '1px solid #333',
  },
  testResult: { fontSize: 13, color: '#aaa' },
  saveBtn: {
    padding: '8px 20px', borderRadius: 6, border: 'none',
    background: '#6c5ce7', color: '#fff', cursor: 'pointer', fontSize: 14,
  },
  loading: { padding: 40, textAlign: 'center', color: '#888' },
};
