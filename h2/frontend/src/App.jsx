import React, { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import BrailleDisplay from './components/BrailleDisplay';
import BrailleEditor from './components/BrailleEditor';
import StaffNotation from './components/StaffNotation';
import MidiPlayer from './components/MidiPlayer';

function App() {
  const [file, setFile] = useState(null);
  const [filename, setFilename] = useState('');
  const [parsedData, setParsedData] = useState(null);
  const [midiUrl, setMidiUrl] = useState('');
  const [musicxmlUrl, setMusicxmlUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [activeTab, setActiveTab] = useState('braille');
  const [showEditor, setShowEditor] = useState(false);
  const [voiceInfo, setVoiceInfo] = useState(null);
  const [multiVoice, setMultiVoice] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  }, []);

  const handleFileSelect = (file) => {
    const validExtensions = ['.braille', '.brl', '.txt'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExtensions.includes(ext)) {
      setError('请上传 .braille, .brl, 或 .txt 格式的文件');
      return;
    }
    setFile(file);
    setFilename(file.name);
    setError('');
    setSuccess('');
    setParsedData(null);
    setMidiUrl('');
    setMusicxmlUrl('');
    setShowEditor(false);
    setVoiceInfo(null);
  };

  const handleInputChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  };

  const parseFile = async () => {
    if (!file) return;

    setLoading(true);
    setError('');
    setSuccess('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/braille/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setParsedData(response.data.parsed);
        setSuccess(`文件解析成功！共识别 ${response.data.parsed.totalNotes} 个音符`);

        if (response.data.parsed.trimmed) {
          const trimmed = response.data.parsed.trimmed;
          if (trimmed.events || trimmed.tokens || trimmed.measures) {
            setSuccess(prev => prev + ' (文件过大，部分数据已裁剪显示)');
          }
        }

        const midiResponse = await axios.post('/api/braille/midi', {
          parsed: response.data.parsed,
          filename: filename,
          options: {
            tempo: response.data.parsed.meta.tempo,
            timeSignature: response.data.parsed.meta.timeSignature,
            multiVoice: multiVoice,
          },
        });

        if (midiResponse.data.success) {
          setMidiUrl(midiResponse.data.midiUrl);
        }

        if (multiVoice) {
          const voiceResponse = await axios.post('/api/braille/separate-voices', {
            parsed: response.data.parsed,
          });
          if (voiceResponse.data.success) {
            setVoiceInfo(voiceResponse.data);
          }
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || '解析文件时发生错误');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyChanges = async (newTokens) => {
    setLoading(true);
    try {
      const response = await axios.post('/api/braille/reparse', {
        tokens: newTokens,
      });

      if (response.data.success) {
        setParsedData(response.data.parsed);
        setSuccess(`重新解析成功！共识别 ${response.data.parsed.totalNotes} 个音符`);

        const midiResponse = await axios.post('/api/braille/midi', {
          parsed: response.data.parsed,
          filename: filename,
          options: {
            tempo: response.data.parsed.meta.tempo,
            timeSignature: response.data.parsed.meta.timeSignature,
            multiVoice: multiVoice,
          },
        });

        if (midiResponse.data.success) {
          setMidiUrl(midiResponse.data.midiUrl);
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || '重新解析时发生错误');
    } finally {
      setLoading(false);
    }
  };

  const handleResetEditor = () => {
    setShowEditor(false);
  };

  const handleExportMusicXML = async () => {
    if (!parsedData) return;
    setLoading(true);
    try {
      const response = await axios.post('/api/braille/musicxml', {
        parsed: parsedData,
        title: parsedData.meta?.title,
        composer: parsedData.meta?.composer,
      });

      if (response.data.success) {
        setMusicxmlUrl(response.data.musicxmlUrl);
        setSuccess('MusicXML 导出成功！');
        window.open(response.data.musicxmlUrl, '_blank');
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || '导出MusicXML时发生错误');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleMultiVoice = async (enabled) => {
    setMultiVoice(enabled);
    if (parsedData) {
      setLoading(true);
      try {
        const midiResponse = await axios.post('/api/braille/midi', {
          parsed: parsedData,
          filename: filename,
          options: {
            tempo: parsedData.meta.tempo,
            timeSignature: parsedData.meta.timeSignature,
            multiVoice: enabled,
          },
        });

        if (midiResponse.data.success) {
          setMidiUrl(midiResponse.data.midiUrl);
        }

        if (enabled) {
          const voiceResponse = await axios.post('/api/braille/separate-voices', {
            parsed: parsedData,
          });
          if (voiceResponse.data.success) {
            setVoiceInfo(voiceResponse.data);
          }
        } else {
          setVoiceInfo(null);
        }
      } catch (err) {
        setError(err.response?.data?.error || err.message || '重新生成MIDI时发生错误');
      } finally {
        setLoading(false);
      }
    }
  };

  const notes = parsedData?.events?.filter(e => e.type === 'note') || [];

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>🎹 盲文乐谱转MIDI转换器</h1>
        <p>上传 .braille 格式文件，实时解析为五线谱并生成MIDI音乐</p>
      </header>

      <div className="main-content">
        <div className="panel">
          <h2 className="panel-title">📁 文件上传与解析</h2>

          <div
            className={`upload-area ${isDragging ? 'dragover' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="upload-icon">📄</div>
            <div className="upload-text">
              {file ? `已选择文件: ${filename}` : '点击或拖拽 .braille 文件到此处'}
            </div>
            <div className="upload-hint">支持 .braille, .brl, .txt 格式</div>
            <input
              ref={fileInputRef}
              type="file"
              className="file-input"
              accept=".braille,.brl,.txt"
              onChange={handleInputChange}
            />
          </div>

          {file && (
            <div className="file-info">
              <span className="file-name">📄 {filename}</span>
              <button
                className="parse-btn"
                onClick={parseFile}
                disabled={loading}
              >
                {loading ? '解析中...' : '🔍 解析文件'}
              </button>
            </div>
          )}

          {parsedData && (
            <div style={{ display: 'flex', gap: 10, marginTop: 15, flexWrap: 'wrap' }}>
              <button
                className={`control-btn ${showEditor ? 'primary' : 'secondary'}`}
                onClick={() => setShowEditor(!showEditor)}
                style={{ padding: '8px 16px', fontSize: '0.9rem' }}
              >
                ✏️ 编辑盲文
              </button>
              <button
                className={`control-btn ${multiVoice ? 'primary' : 'secondary'}`}
                onClick={() => handleToggleMultiVoice(!multiVoice)}
                style={{ padding: '8px 16px', fontSize: '0.9rem' }}
              >
                🎵 多声部 {multiVoice ? '✓' : ''}
              </button>
              <button
                className="control-btn secondary"
                onClick={handleExportMusicXML}
                disabled={loading}
                style={{ padding: '8px 16px', fontSize: '0.9rem' }}
              >
                📥 导出MusicXML
              </button>
            </div>
          )}

          {error && <div className="error-message">❌ {error}</div>}
          {success && <div className="success-message">✅ {success}</div>}

          {voiceInfo && (
            <div style={{ marginTop: 15, background: '#f0fff4', padding: 15, borderRadius: 8 }}>
              <h4 style={{ margin: '0 0 10px 0', color: '#2f855a' }}>🎵 声部分离信息</h4>
              <div style={{ display: 'flex', gap: 15, flexWrap: 'wrap' }}>
                {voiceInfo.voices?.map((voice, idx) => (
                  <div key={idx} style={{ background: 'white', padding: 10, borderRadius: 6, border: '1px solid #e2e8f0' }}>
                    <strong>{voice.name}</strong>
                    <div style={{ fontSize: '0.85rem', color: '#718096' }}>
                      谱号: {voice.clef === 'treble' ? '高音谱号' : '低音谱号'}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#718096' }}>
                      音符: {voice.noteCount} 个
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {parsedData && (
            <div style={{ marginTop: 20 }}>
              <h2 className="panel-title">📊 解析信息</h2>
              <div className="meta-info">
                <div className="meta-item">
                  <div className="meta-label">标题</div>
                  <div className="meta-value">{parsedData.meta?.title || '未命名'}</div>
                </div>
                <div className="meta-item">
                  <div className="meta-label">作曲家</div>
                  <div className="meta-value">{parsedData.meta?.composer || '未知'}</div>
                </div>
                <div className="meta-item">
                  <div className="meta-label">速度 (BPM)</div>
                  <div className="meta-value">{parsedData.meta?.tempo || 120}</div>
                </div>
                <div className="meta-item">
                  <div className="meta-label">拍号</div>
                  <div className="meta-value">
                    {parsedData.meta?.timeSignature?.beats || 4}/{parsedData.meta?.timeSignature?.unit || 4}
                  </div>
                </div>
                <div className="meta-item">
                  <div className="meta-label">音符数量</div>
                  <div className="meta-value">{parsedData.totalNotes || 0}</div>
                </div>
                <div className="meta-item">
                  <div className="meta-label">小节数</div>
                  <div className="meta-value">{parsedData.measures?.length || 0}</div>
                </div>
              </div>
            </div>
          )}

          {parsedData && (
            <div style={{ marginTop: 20 }}>
              <h2 className="panel-title">🎵 音符列表</h2>
              <div className="note-list">
                {notes.length > 0 ? (
                  notes.slice(0, 50).map((note, idx) => (
                    <div key={idx} className="note-item">
                      <span className="note-pitch">{note.pitch}</span>
                      <span className="note-duration">
                        MIDI: {note.midiNote} | 时长: {note.duration}拍 | 力度: {note.velocity}
                      </span>
                      <span className="note-measure">第{note.measure + 1}小节</span>
                    </div>
                  ))
                ) : (
                  <div style={{ textAlign: 'center', color: '#718096', padding: 20 }}>
                    没有识别到音符
                  </div>
                )}
                {notes.length > 50 && (
                  <div style={{ textAlign: 'center', color: '#718096', padding: 10, fontSize: '0.9rem' }}>
                    ... 还有 {notes.length - 50} 个音符
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <button
              className={`control-btn ${activeTab === 'braille' ? 'primary' : 'secondary'}`}
              onClick={() => setActiveTab('braille')}
              style={{ padding: '8px 16px', fontSize: '0.95rem' }}
            >
              ⠿ 盲文点阵
            </button>
            <button
              className={`control-btn ${activeTab === 'staff' ? 'primary' : 'secondary'}`}
              onClick={() => setActiveTab('staff')}
              style={{ padding: '8px 16px', fontSize: '0.95rem' }}
            >
              🎼 五线谱
            </button>
          </div>

          {activeTab === 'braille' && (
            <>
              <h2 className="panel-title">
                {showEditor ? '✏️ 盲文点阵编辑器' : '⠿ 盲文点阵预览'}
              </h2>
              {showEditor ? (
                <BrailleEditor
                  tokens={parsedData?.tokens || []}
                  events={parsedData?.events || []}
                  onCellChange={() => {}}
                  onApplyChanges={handleApplyChanges}
                  onReset={handleResetEditor}
                />
              ) : (
                <BrailleDisplay
                  tokens={parsedData?.tokens || []}
                  events={parsedData?.events || []}
                />
              )}
            </>
          )}

          {activeTab === 'staff' && (
            <>
              <h2 className="panel-title">🎼 五线谱预览</h2>
              {parsedData ? (
                <StaffNotation parsedData={parsedData} />
              ) : (
                <div style={{
                  background: '#f7fafc',
                  borderRadius: 8,
                  padding: 60,
                  textAlign: 'center',
                  color: '#718096',
                  minHeight: 200,
                }}>
                  上传并解析文件后将显示五线谱预览
                </div>
              )}
            </>
          )}

          {parsedData && (
            <div style={{ marginTop: 20 }}>
              <h2 className="panel-title">🎧 MIDI播放控制</h2>
              <MidiPlayer midiUrl={midiUrl} parsedData={parsedData} />
            </div>
          )}

          {parsedData?.trimmed && (parsedData.trimmed.events || parsedData.trimmed.tokens) && (
            <div className="error-message" style={{ marginTop: 15 }}>
              ⚠️ 注意：文件过大，部分显示数据已裁剪。MIDI生成将使用完整数据。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
