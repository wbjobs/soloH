import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Music,
  Calendar,
  FileText,
  Trash2,
  ChevronRight,
  Upload,
  X,
  Loader2,
} from 'lucide-react';
import { listScores, deleteScore, createScore, stitchPages } from '@/services/api';
import type { ScoreListItem } from '@/types/index';

const LibraryPage: React.FC = () => {
  const [scores, setScores] = useState<ScoreListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [title, setTitle] = useState('');
  const [composer, setComposer] = useState('');
  const [dynasty, setDynasty] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stitching, setStitching] = useState(false);

  useEffect(() => {
    loadScores();
  }, []);

  const loadScores = async () => {
    try {
      setLoading(true);
      const data = await listScores();
      setScores(data);
    } catch (error) {
      console.error('Failed to load scores:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
    if (files.length > 0) {
      setTitle(files[0].name.replace(/\.[^/.]+$/, ''));
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStitchPreview = async () => {
    if (selectedFiles.length < 2) return;
    try {
      setStitching(true);
      const result = await stitchPages(selectedFiles);
      if (result.success) {
        setPreviewUrl(`http://localhost:5000${result.stitched_url}`);
      }
    } catch (error) {
      console.error('Failed to stitch pages:', error);
    } finally {
      setStitching(false);
    }
  };

  const handleCreateScore = async () => {
    if (!title || selectedFiles.length === 0) return;

    try {
      setCreating(true);
      const metadata = {
        composer,
        dynasty,
        description,
      };
      const result = await createScore(title, selectedFiles, undefined, metadata);
      if (result.success) {
        setShowCreateModal(false);
        setSelectedFiles([]);
        setTitle('');
        setComposer('');
        setDynasty('');
        setDescription('');
        setPreviewUrl(null);
        loadScores();
      }
    } catch (error) {
      console.error('Failed to create score:', error);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (scoreId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('确定要删除此曲目吗？')) return;

    try {
      await deleteScore(scoreId);
      loadScores();
    } catch (error) {
      console.error('Failed to delete score:', error);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getDifficultyColor = (difficulty: string) => {
    const colors: Record<string, string> = {
      入门级: 'bg-green-100 text-green-800',
      初级: 'bg-lime-100 text-lime-800',
      中级: 'bg-yellow-100 text-yellow-800',
      高级: 'bg-orange-100 text-orange-800',
      演奏级: 'bg-red-100 text-red-800',
    };
    return colors[difficulty] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="min-h-screen bg-[#F5F0E6]">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-[#4A2C1A] mb-2">曲谱库</h1>
            <p className="text-[#4A2C1A]/70">管理和浏览已数字化的古琴减字谱</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-[#C0392B] text-white px-6 py-3 rounded-lg hover:bg-[#A93226] transition-colors shadow-lg"
          >
            <Plus size={20} />
            新建曲目
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-[#C0392B]" size={40} />
          </div>
        ) : scores.length === 0 ? (
          <div className="text-center py-20 bg-white/50 rounded-2xl border-2 border-dashed border-[#4A2C1A]/20">
            <Music size={64} className="mx-auto text-[#4A2C1A]/30 mb-4" />
            <p className="text-[#4A2C1A]/60 text-lg mb-2">暂无曲目</p>
            <p className="text-[#4A2C1A]/40">点击"新建曲目"开始数字化您的第一份减字谱</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {scores.map((score) => (
              <div
                key={score.id}
                className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-[#4A2C1A]/10 group"
              >
                <Link to={`/score/${score.id}`} className="block">
                  <div className="h-40 bg-gradient-to-br from-[#4A2C1A]/10 to-[#C0392B]/10 flex items-center justify-center relative overflow-hidden">
                    <img
                      src={`http://localhost:5000/api/score/${score.id}/stitched`}
                      alt={score.title}
                      className="w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                    <Music size={48} className="absolute text-[#4A2C1A]/40" />
                  </div>
                  <div className="p-5">
                    <div className="flex justify-between items-start mb-3">
                      <h3 className="text-xl font-semibold text-[#4A2C1A] truncate">
                        {score.title}
                      </h3>
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(
                          score.difficulty
                        )}`}
                      >
                        {score.difficulty}
                      </span>
                    </div>
                    <div className="space-y-2 text-sm text-[#4A2C1A]/70">
                      <div className="flex items-center gap-2">
                        <FileText size={14} />
                        <span>{score.composer}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar size={14} />
                        <span>{formatDate(score.created_at)}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <span>{score.total_pages}页</span>
                        <span>{score.total_jianzi}个减字</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-[#4A2C1A]/10">
                      <span className="text-[#C0392B] text-sm font-medium flex items-center gap-1">
                        查看详情
                        <ChevronRight size={16} />
                      </span>
                      <button
                        onClick={(e) => handleDelete(score.id, e)}
                        className="p-2 text-[#4A2C1A]/40 hover:text-[#C0392B] hover:bg-[#C0392B]/10 rounded-lg transition-colors"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-[#4A2C1A]/10 flex justify-between items-center">
              <h2 className="text-2xl font-bold text-[#4A2C1A]">新建曲目</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 hover:bg-[#4A2C1A]/10 rounded-lg transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                  上传谱页图片（支持多页）
                </label>
                <div className="border-2 border-dashed border-[#4A2C1A]/20 rounded-xl p-8 text-center hover:border-[#C0392B]/50 transition-colors">
                  <input
                    type="file"
                    id="page-upload"
                    multiple
                    accept="image/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <label
                    htmlFor="page-upload"
                    className="cursor-pointer flex flex-col items-center"
                  >
                    <Upload size={48} className="text-[#4A2C1A]/40 mb-3" />
                    <p className="text-[#4A2C1A]/70 mb-1">点击或拖拽上传谱页图片</p>
                    <p className="text-[#4A2C1A]/40 text-sm">支持 PNG, JPG, JPEG 格式</p>
                  </label>
                </div>

                {selectedFiles.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between items-center">
                      <p className="text-sm text-[#4A2C1A]/70">
                        已选择 {selectedFiles.length} 个文件
                      </p>
                      {selectedFiles.length >= 2 && (
                        <button
                          onClick={handleStitchPreview}
                          disabled={stitching}
                          className="text-sm text-[#C0392B] hover:underline disabled:opacity-50"
                        >
                          {stitching ? '拼接中...' : '预览拼接效果'}
                        </button>
                      )}
                    </div>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {selectedFiles.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between bg-[#4A2C1A]/5 rounded-lg px-3 py-2"
                        >
                          <span className="text-sm text-[#4A2C1A] truncate">
                            {index + 1}. {file.name}
                          </span>
                          <button
                            onClick={() => removeFile(index)}
                            className="p-1 hover:bg-[#C0392B]/10 rounded"
                          >
                            <X size={14} className="text-[#C0392B]" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {previewUrl && (
                  <div className="mt-4">
                    <p className="text-sm text-[#4A2C1A]/70 mb-2">拼接预览：</p>
                    <img
                      src={previewUrl}
                      alt="Stitched preview"
                      className="w-full rounded-lg border border-[#4A2C1A]/20"
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                    曲目名称 *
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="如：流水"
                    className="w-full px-4 py-2 border border-[#4A2C1A]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C0392B]/30"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                    作曲/传谱者
                  </label>
                  <input
                    type="text"
                    value={composer}
                    onChange={(e) => setComposer(e.target.value)}
                    placeholder="如：俞伯牙"
                    className="w-full px-4 py-2 border border-[#4A2C1A]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C0392B]/30"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[#4A2C1A] mb-2">朝代</label>
                <input
                  type="text"
                  value={dynasty}
                  onChange={(e) => setDynasty(e.target.value)}
                  placeholder="如：春秋"
                  className="w-full px-4 py-2 border border-[#4A2C1A]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C0392B]/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                  曲目简介
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="请输入曲目简介..."
                  className="w-full px-4 py-2 border border-[#4A2C1A]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C0392B]/30 resize-none"
                />
              </div>
            </div>

            <div className="p-6 border-t border-[#4A2C1A]/10 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-6 py-2 text-[#4A2C1A] hover:bg-[#4A2C1A]/10 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreateScore}
                disabled={creating || !title || selectedFiles.length === 0}
                className="flex items-center gap-2 px-6 py-2 bg-[#C0392B] text-white rounded-lg hover:bg-[#A93226] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating && <Loader2 size={18} className="animate-spin" />}
                {creating ? '创建中...' : '创建曲目'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LibraryPage;
