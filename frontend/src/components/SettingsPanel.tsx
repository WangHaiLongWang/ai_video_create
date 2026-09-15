import React, { useState, useEffect } from 'react';

interface ProviderInfo {
  name: string;
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
  dashscope_api_url: string;
  dashscope_image_model: string;
  dashscope_image_size: string;
  dashscope_use_async: boolean;
  dashscope_prompt_extend: boolean;
  dashscope_prompt_extend_mode: string;
  dashscope_enable_thinking: boolean;
  dashscope_watermark: boolean;
  comfyui_api_url: string;
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
        setComfyuiUrl(s.comfyui_api_url);
        setDashscopeUrl(s.dashscope_api_url);
        setDashscopeImageModel(s.dashscope_image_model);
        setDashscopeImageSize(s.dashscope_image_size);
        setDashscopeUseAsync(s.dashscope_use_async);
        setDashscopePromptExtend(s.dashscope_prompt_extend);
        setDashscopePromptExtendMode(s.dashscope_prompt_extend_mode);
        setDashscopeEnableThinking(s.dashscope_enable_thinking);
        setDashscopeWatermark(s.dashscope_watermark);
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
            </select>

            <label style={styles.label}>图像生成</label>
            <select style={styles.select} value={imageProvider} onChange={(e) => setImageProvider(e.target.value)}>
              <option value="mock">Mock (测试)</option>
              <option value="comfyui">ComfyUI</option>
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

          {/* ComfyUI Config */}
          {imageProvider === 'comfyui' && (
            <section style={styles.section}>
              <h3 style={styles.sectionTitle}>🎨 ComfyUI 配置</h3>
              <label style={styles.label}>API URL</label>
              <input style={styles.input} value={comfyuiUrl} onChange={(e) => setComfyuiUrl(e.target.value)} />
              <button style={styles.testBtn} onClick={() => handleTestProvider('comfyui')}>测试连接</button>
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
                <strong>{p.name}</strong>
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
