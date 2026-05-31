"""
FastAPI接口层
提供作者归属预测、风格分析等API服务
"""

import os
import sys
import numpy as np
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Body
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from author_authorship import (
    FeatureExtractor,
    AuthorClassifier,
    StyleDriftAnalyzer,
    StyleVisualizer,
    PrototypicalNetwork,
    CrossLanguageClassifier,
    DialogueSeparator,
    CharacterStyleAnalyzer,
    NarrativePerspectiveDetector
)


app = FastAPI(
    title="小说作者归属分析 API",
    description="基于Python + scikit-learn + spaCy的小说作者归属分析系统",
    version="1.0.0"
)


feature_extractor = None
author_classifier = None
style_drift_analyzer = None
style_visualizer = None
prototypical_network = None
cross_language_classifier = None
dialogue_separator = None
character_style_analyzer = None
narrative_perspective_detector = None

MODEL_DIR = os.path.join(os.path.dirname(__file__), "author_authorship", "data", "models")
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "author_classifier.joblib")
PROTONET_PATH = os.path.join(MODEL_DIR, "prototypical_network.joblib")
CROSS_LANG_PATH = os.path.join(MODEL_DIR, "cross_language_classifier.joblib")


class PredictionRequest(BaseModel):
    text: str = Field(..., description="小说文本内容")
    return_all_authors: bool = Field(False, description="是否返回所有作者的概率")
    use_protonet: bool = Field(False, description="是否使用原型网络进行预测")


class BatchPredictionRequest(BaseModel):
    texts: List[str] = Field(..., description="小说文本列表")
    use_protonet: bool = Field(False, description="是否使用原型网络进行预测")


class AddAuthorRequest(BaseModel):
    author_name: str = Field(..., description="新作者名称")
    samples: List[str] = Field(..., description="作者作品样本文本列表（建议3-5个）")
    update_global_stats: bool = Field(False, description="是否更新全局统计量")


class StyleDriftRequest(BaseModel):
    works: List[str] = Field(..., description="同一作者的作品文本列表，按时间顺序排列")
    work_titles: Optional[List[str]] = Field(None, description="作品标题列表")


class DivergenceRequest(BaseModel):
    text1: str = Field(..., description="文本1")
    text2: str = Field(..., description="文本2")


class VisualizationRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表")
    labels: List[str] = Field(..., description="标签列表")
    authors: Optional[List[str]] = Field(None, description="作者列表")
    viz_type: str = Field("tsne", description="可视化类型: tsne, pca, parallel, radar, heatmap")
    use_plotly: bool = Field(True, description="是否使用Plotly交互式图表")


class CrossLanguagePredictRequest(BaseModel):
    text: str = Field(..., description="输入文本（任何支持的语言）")
    return_all_distances: bool = Field(False, description="是否返回所有作者的距离")


class CrossLanguageVerifyRequest(BaseModel):
    text1: str = Field(..., description="文本1（语言A）")
    text2: str = Field(..., description="文本2（语言B）")
    author: Optional[str] = Field(None, description="可选，假设的作者")


class CrossLanguageTrainRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表（可跨语言）")
    authors: List[str] = Field(..., description="作者标签列表")
    languages: Optional[List[str]] = Field(None, description="可选，文本语言列表")


class CharacterAnalysisRequest(BaseModel):
    text: str = Field(..., description="小说文本内容")
    return_detailed_features: bool = Field(True, description="是否返回详细特征")


class CharacterCompareRequest(BaseModel):
    profile1_name: str = Field(..., description="角色1名称")
    profile2_name: str = Field(..., description="角色2名称")
    text: str = Field(..., description="包含两个角色对话的文本")


class PerspectiveDetectRequest(BaseModel):
    text: str = Field(..., description="小说文本内容")
    exclude_dialogue: bool = Field(True, description="是否从叙述文本中排除对话")


@app.on_event("startup")
async def load_models():
    """启动时加载模型"""
    global feature_extractor, author_classifier
    global style_drift_analyzer, style_visualizer, prototypical_network
    global cross_language_classifier, dialogue_separator
    global character_style_analyzer, narrative_perspective_detector
    
    try:
        feature_extractor = FeatureExtractor()
    except Exception as e:
        print(f"Warning: Failed to load spaCy model: {e}")
        print("Falling back to basic feature extraction...")
        feature_extractor = FeatureExtractor(spacy_model='en_core_web_sm')
    
    style_drift_analyzer = StyleDriftAnalyzer(feature_extractor)
    style_visualizer = StyleVisualizer(feature_extractor)
    prototypical_network = PrototypicalNetwork()
    dialogue_separator = DialogueSeparator()
    character_style_analyzer = CharacterStyleAnalyzer(feature_extractor)
    narrative_perspective_detector = NarrativePerspectiveDetector()
    cross_language_classifier = CrossLanguageClassifier()
    
    if os.path.exists(CLASSIFIER_PATH):
        try:
            author_classifier = AuthorClassifier.load(CLASSIFIER_PATH)
            print(f"Loaded classifier from {CLASSIFIER_PATH}")
        except Exception as e:
            print(f"Warning: Failed to load classifier: {e}")
            author_classifier = AuthorClassifier()
    else:
        author_classifier = AuthorClassifier()
        print("Initialized new classifier")
    
    if os.path.exists(PROTONET_PATH):
        try:
            prototypical_network = PrototypicalNetwork.load(PROTONET_PATH)
            print(f"Loaded prototypical network from {PROTONET_PATH}")
        except Exception as e:
            print(f"Warning: Failed to load prototypical network: {e}")
    
    if os.path.exists(CROSS_LANG_PATH):
        try:
            cross_language_classifier = CrossLanguageClassifier.load(CROSS_LANG_PATH)
            print(f"Loaded cross-language classifier from {CROSS_LANG_PATH}")
        except Exception as e:
            print(f"Warning: Failed to load cross-language classifier: {e}")


@app.on_event("shutdown")
async def save_models():
    """关闭时保存模型"""
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    if author_classifier and author_classifier._fitted:
        try:
            author_classifier.save(CLASSIFIER_PATH)
            print(f"Saved classifier to {CLASSIFIER_PATH}")
        except Exception as e:
            print(f"Warning: Failed to save classifier: {e}")
    
    if prototypical_network and prototypical_network._fitted:
        try:
            prototypical_network.save(PROTONET_PATH)
            print(f"Saved prototypical network to {PROTONET_PATH}")
        except Exception as e:
            print(f"Warning: Failed to save prototypical network: {e}")
    
    if cross_language_classifier and cross_language_classifier._fitted:
        try:
            cross_language_classifier.save(CROSS_LANG_PATH)
            print(f"Saved cross-language classifier to {CROSS_LANG_PATH}")
        except Exception as e:
            print(f"Warning: Failed to save cross-language classifier: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径，返回API文档链接"""
    return """
    <html>
        <head>
            <title>小说作者归属分析 API</title>
        </head>
        <body>
            <h1>小说作者归属分析系统 API</h1>
            <p>基于Python + scikit-learn + spaCy实现</p>
            <ul>
                <li><a href="/docs">API 文档 (Swagger UI)</a></li>
                <li><a href="/redoc">API 文档 (ReDoc)</a></li>
            </ul>
            <h2>主要功能:</h2>
            <ul>
                <li>作者归属预测（支持200位作家）</li>
                <li>风格特征向量提取</li>
                <li>时序风格漂移分析</li>
                <li>可视化（平行坐标图、t-SNE聚类）</li>
                <li>小样本学习添加新作者</li>
            </ul>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "feature_extractor_loaded": feature_extractor is not None,
        "classifier_fitted": author_classifier._fitted if author_classifier else False,
        "protonet_fitted": prototypical_network._fitted if prototypical_network else False,
        "cross_lang_fitted": cross_language_classifier._fitted if cross_language_classifier else False,
        "num_authors_in_classifier": len(author_classifier.get_author_list()) if author_classifier else 0,
        "num_authors_in_protonet": prototypical_network.get_num_authors() if prototypical_network else 0,
        "num_authors_in_cross_lang": len(cross_language_classifier.author_prototypes) if cross_language_classifier else 0,
        "new_features_available": {
            "cross_language": cross_language_classifier is not None,
            "character_analysis": character_style_analyzer is not None,
            "perspective_detection": narrative_perspective_detector is not None
        }
    }


@app.post("/predict")
async def predict_author(request: PredictionRequest):
    """
    预测小说作者归属（包含置信度校准）
    
    返回预测作者、校准后的置信度、风格距离等信息
    自动进行文本长度归一化、体裁校正、文本类型校正
    """
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    try:
        text_metadata = feature_extractor.get_text_metadata(request.text)
        features = feature_extractor.extract_features(request.text)
        features = features.reshape(1, -1)
        
        if request.use_protonet:
            if not prototypical_network or not prototypical_network._fitted:
                raise HTTPException(status_code=400, 
                                   detail="Prototypical network not trained. Add authors first using /add_author.")
            
            results = prototypical_network.predict_with_confidence(features)
            result = results[0]
            
            response = {
                "predicted_author": result["predicted_author"],
                "confidence": result["confidence"],
                "top_predictions": result["top_predictions"],
                "style_distances": result["distances"],
                "model_used": "prototypical_network",
                "feature_vector": features[0].tolist(),
                "feature_names": feature_extractor.get_feature_names(),
                "text_metadata": text_metadata
            }
        else:
            if not author_classifier or not author_classifier._fitted:
                raise HTTPException(status_code=400, 
                                   detail="Classifier not trained. Train the model first or use prototypical network.")
            
            results = author_classifier.predict_with_confidence(
                features, text_metadata=[text_metadata]
            )
            result = results[0]
            
            if not request.return_all_authors:
                result["style_distances"] = dict(
                    sorted(result["style_distances"].items(), 
                          key=lambda x: x[1]["cosine"])[:10]
                )
            
            response = {
                "predicted_author": result["predicted_author"],
                "confidence": result["confidence"],
                "raw_confidence": result.get("raw_confidence", result["confidence"]),
                "confidence_calibration": result.get("confidence_calibration", {}),
                "top_predictions": result["top_predictions"],
                "style_distances": result["style_distances"],
                "model_used": "ensemble_classifier",
                "feature_vector": features[0].tolist(),
                "feature_names": feature_extractor.get_feature_names(),
                "text_metadata": text_metadata
            }
        
        return JSONResponse(content=response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch")
async def batch_predict(request: BatchPredictionRequest):
    """批量预测作者归属（包含置信度校准）"""
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    try:
        text_metadata_list = [feature_extractor.get_text_metadata(text) 
                             for text in request.texts]
        features = feature_extractor.extract_batch(request.texts)
        
        if request.use_protonet:
            if not prototypical_network or not prototypical_network._fitted:
                raise HTTPException(status_code=400, 
                                   detail="Prototypical network not trained.")
            
            results = prototypical_network.predict_with_confidence(features)
            model_used = "prototypical_network"
        else:
            if not author_classifier or not author_classifier._fitted:
                raise HTTPException(status_code=400, 
                                   detail="Classifier not trained.")
            
            results = author_classifier.predict_with_confidence(
                features, text_metadata=text_metadata_list
            )
            model_used = "ensemble_classifier"
        
        predictions = []
        for i, result in enumerate(results):
            pred = {
                "text_index": i,
                "predicted_author": result["predicted_author"],
                "confidence": result["confidence"],
                "raw_confidence": result.get("raw_confidence", result["confidence"]),
                "confidence_calibration": result.get("confidence_calibration", {}),
                "text_metadata": text_metadata_list[i],
                "top_predictions": result["top_predictions"]
            }
            predictions.append(pred)
        
        return {
            "model_used": model_used,
            "num_texts": len(request.texts),
            "predictions": predictions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/features")
async def extract_features(text: str = Body(..., embed=True)):
    """提取文本的风格特征向量（包含文本类型和体裁检测）"""
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    try:
        text_metadata = feature_extractor.get_text_metadata(text)
        features = feature_extractor.extract_features(text)
        feature_names = feature_extractor.get_feature_names()
        feature_groups = feature_extractor.get_feature_groups()
        
        feature_dict = {}
        for group_name, group_features in feature_groups.items():
            group_indices = [feature_names.index(f) for f in group_features if f in feature_names]
            feature_dict[group_name] = {
                f: float(features[idx]) for idx, f in zip(group_indices, group_features)
                if idx < len(features)
            }
        
        return {
            "feature_vector": features.tolist(),
            "feature_names": feature_names,
            "feature_groups": feature_dict,
            "feature_dim": len(features),
            "text_metadata": text_metadata,
            "text_type": "dialogue" if text_metadata['dialogue_ratio'] > 0.6 else 
                        "narrative" if text_metadata['narrative_ratio'] > 0.6 else "mixed",
            "genre": "poetry" if text_metadata['poetry_score'] > 0.5 else "prose"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add_author")
async def add_new_author(request: AddAuthorRequest):
    """
    添加新作者（小样本学习）
    
    使用原型网络，只需少量样本（建议3-5个）即可添加新作者
    """
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    if not prototypical_network:
        raise HTTPException(status_code=500, detail="Prototypical network not initialized")
    
    try:
        if len(request.samples) < 1:
            raise HTTPException(status_code=400, 
                               detail="At least one sample is required")
        
        sample_features = []
        for sample in request.samples:
            feat = feature_extractor.extract_features(sample)
            sample_features.append(feat)
        
        result = prototypical_network.add_new_author(
            author_name=request.author_name,
            sample_features=sample_features,
            update_global_stats=request.update_global_stats
        )
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        prototypical_network.save(PROTONET_PATH)
        
        return {
            "status": "success",
            "message": f"Author '{request.author_name}' added successfully",
            "details": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/style_drift")
async def analyze_style_drift(request: StyleDriftRequest):
    """
    分析同一作者不同作品的风格漂移
    
    计算时序风格变化，包括散度矩阵、累积漂移、漂移速率等
    """
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    if not style_drift_analyzer:
        raise HTTPException(status_code=500, detail="Style drift analyzer not initialized")
    
    try:
        if len(request.works) < 2:
            raise HTTPException(status_code=400, 
                               detail="At least 2 works are required for temporal analysis")
        
        work_features = []
        for work in request.works:
            feat = feature_extractor.extract_features(work)
            work_features.append(feat)
        
        drift_analysis = style_drift_analyzer.analyze_temporal_drift(
            works_features=work_features,
            work_titles=request.work_titles
        )
        
        change_points = style_drift_analyzer.detect_style_change_points(work_features)
        
        response = {
            "drift_analysis": drift_analysis,
            "style_change_points": change_points,
            "num_works": len(request.works)
        }
        
        return JSONResponse(content=response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/divergence")
async def compute_divergence(request: DivergenceRequest):
    """计算两篇文本之间的风格散度"""
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    if not style_drift_analyzer:
        raise HTTPException(status_code=500, detail="Style drift analyzer not initialized")
    
    try:
        feat1 = feature_extractor.extract_features(request.text1)
        feat2 = feature_extractor.extract_features(request.text2)
        
        divergences = style_drift_analyzer.compute_all_divergences(feat1, feat2)
        group_divergences = style_drift_analyzer.compute_group_divergences(feat1, feat2)
        
        return {
            "overall_divergences": divergences,
            "group_divergences": group_divergences
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/visualize")
async def generate_visualization(request: VisualizationRequest):
    """
    生成可视化图表
    
    支持: tsne, pca, parallel, radar, heatmap
    """
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    if not style_visualizer:
        raise HTTPException(status_code=500, detail="Visualizer not initialized")
    
    try:
        if len(request.texts) != len(request.labels):
            raise HTTPException(status_code=400, 
                               detail="Number of texts and labels must match")
        
        features = feature_extractor.extract_batch(request.texts)
        
        viz_types = {
            "tsne": style_visualizer.tsne_visualization,
            "pca": style_visualizer.pca_visualization,
            "parallel": style_visualizer.parallel_coordinates,
            "radar": style_visualizer.radar_chart,
            "heatmap": style_visualizer.feature_heatmap
        }
        
        if request.viz_type not in viz_types:
            raise HTTPException(status_code=400, 
                               detail=f"Unsupported visualization type. Choose from: {list(viz_types.keys())}")
        
        viz_func = viz_types[request.viz_type]
        
        html_output = viz_func(
            features=features,
            labels=request.labels,
            authors=request.authors,
            use_plotly=request.use_plotly
        )
        
        if request.use_plotly and html_output:
            return HTMLResponse(content=html_output)
        else:
            return {
                "message": "Visualization generated (matplotlib mode)",
                "viz_type": request.viz_type,
                "num_samples": len(request.texts)
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/authors")
async def get_available_authors():
    """获取所有可用作者列表"""
    result = {
        "classifier_authors": [],
        "protonet_authors": [],
        "author_list_reference": []
    }
    
    if author_classifier and author_classifier._fitted:
        result["classifier_authors"] = author_classifier.get_author_list()
    
    if prototypical_network and prototypical_network._fitted:
        result["protonet_authors"] = prototypical_network.get_author_list()
    
    from author_authorship.classifier import AUTHOR_LIST
    result["author_list_reference"] = AUTHOR_LIST
    
    return result


@app.get("/feature_info")
async def get_feature_information():
    """获取特征信息"""
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    feature_names = feature_extractor.get_feature_names()
    feature_groups = feature_extractor.get_feature_groups()
    
    group_sizes = {group: len(features) for group, features in feature_groups.items()}
    
    return {
        "total_features": len(feature_names),
        "feature_groups": feature_groups,
        "group_sizes": group_sizes,
        "feature_names": feature_names
    }


@app.post("/train")
async def train_classifier(texts: List[str] = Body(...), 
                           authors: List[str] = Body(...),
                           use_ensemble: bool = Body(True),
                           enable_length_normalization: bool = Body(True)):
    """训练分类器模型（支持文本长度归一化）"""
    if not feature_extractor:
        raise HTTPException(status_code=500, detail="Feature extractor not initialized")
    
    if not author_classifier:
        raise HTTPException(status_code=500, detail="Classifier not initialized")
    
    try:
        if len(texts) != len(authors):
            raise HTTPException(status_code=400, 
                               detail="Number of texts and authors must match")
        
        if len(texts) < 2:
            raise HTTPException(status_code=400, 
                               detail="At least 2 samples are required for training")
        
        features = feature_extractor.extract_batch(texts)
        
        text_word_counts = None
        if enable_length_normalization:
            text_word_counts = []
            for text in texts:
                meta = feature_extractor.get_text_metadata(text)
                text_word_counts.append(meta['word_count'])
        
        metrics = author_classifier.fit(
            features, authors, 
            use_ensemble=use_ensemble,
            text_word_counts=text_word_counts
        )
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        author_classifier.save(CLASSIFIER_PATH)
        
        return {
            "status": "success",
            "message": "Classifier trained successfully",
            "metrics": metrics,
            "length_normalization_enabled": enable_length_normalization
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cross_language/predict")
async def cross_language_predict(request: CrossLanguagePredictRequest):
    """
    跨语言作者归属预测
    使用多语言BERT嵌入进行跨语言作者预测
    """
    if not cross_language_classifier:
        raise HTTPException(status_code=500, detail="Cross-language classifier not initialized")
    
    if not cross_language_classifier._fitted:
        raise HTTPException(status_code=400, 
                           detail="Cross-language model not trained. Call /cross_language/train first.")
    
    try:
        predicted_author, result = cross_language_classifier.predict(
            request.text, 
            return_all_distances=request.return_all_distances
        )
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cross_language/verify")
async def cross_language_verify(request: CrossLanguageVerifyRequest):
    """
    跨语言作者验证
    判断两篇不同语言的文本是否来自同一作者
    """
    if not cross_language_classifier:
        raise HTTPException(status_code=500, detail="Cross-language classifier not initialized")
    
    try:
        result = cross_language_classifier.cross_language_verify(
            request.text1, 
            request.text2,
            author=request.author
        )
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cross_language/train")
async def cross_language_train(request: CrossLanguageTrainRequest):
    """
    训练跨语言作者分类器
    支持多语言文本训练
    """
    if not cross_language_classifier:
        raise HTTPException(status_code=500, detail="Cross-language classifier not initialized")
    
    try:
        if len(request.texts) != len(request.authors):
            raise HTTPException(status_code=400, 
                               detail="Number of texts and authors must match")
        
        if len(request.texts) < 2:
            raise HTTPException(status_code=400, 
                               detail="At least 2 samples are required for training")
        
        cross_language_classifier.fit(
            texts=request.texts,
            authors=request.authors,
            languages=request.languages
        )
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        cross_language_classifier.save(CROSS_LANG_PATH)
        
        return {
            "status": "success",
            "message": "Cross-language classifier trained successfully",
            "num_authors": len(cross_language_classifier.author_prototypes),
            "language_stats": cross_language_classifier.language_stats
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cross_language/features")
async def cross_language_extract_features(text: str = Body(..., embed=True),
                                        use_bert: bool = Body(True)):
    """
    提取跨语言特征
    返回语言检测结果、语言无关特征、BERT嵌入等
    """
    if not cross_language_classifier:
        raise HTTPException(status_code=500, detail="Cross-language classifier not initialized")
    
    try:
        result = cross_language_classifier.extract_cross_language_features(
            text, use_bert=use_bert
        )
        
        return {
            "language": result['language'],
            "language_confidence": result['language_confidence'],
            "language_agnostic_features": result['language_agnostic'].tolist(),
            "bert_embedding_dim": len(result['bert_embedding']),
            "bert_embedding_preview": result['bert_embedding'][:10].tolist(),
            "combined_feature_dim": len(result['combined'])
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/character/analyze")
async def analyze_characters(request: CharacterAnalysisRequest):
    """
    角色对话分离与风格分析
    自动提取文本中的角色对话，分析每个角色的语言风格
    """
    if not character_style_analyzer:
        raise HTTPException(status_code=500, detail="Character style analyzer not initialized")
    
    try:
        character_profiles = character_style_analyzer.analyze(request.text)
        
        result = {
            "num_characters": len(character_profiles),
            "characters": {}
        }
        
        for name, profile in character_profiles.items():
            char_data = {
                "name": name,
                "num_utterances": len(profile.utterances),
                "total_words": profile.total_words,
                "avg_utterance_length": profile.avg_utterance_length,
                "speaking_frequency": profile.speaking_frequency
            }
            
            if request.return_detailed_features:
                char_data["style_features"] = profile.style_features
            
            utterances_preview = []
            for utt in profile.utterances[:5]:
                utterances_preview.append({
                    "text": utt.text[:100],
                    "line_number": utt.line_number
                })
            char_data["utterances_preview"] = utterances_preview
            
            result["characters"][name] = char_data
        
        utterances = character_style_analyzer.dialogue_separator.extract_dialogues(request.text)
        result["total_dialogues"] = len(utterances)
        result["narrative_text"] = character_style_analyzer.get_narrative_text(request.text)[:500]
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/character/compare")
async def compare_characters(request: CharacterCompareRequest):
    """
    比较两个角色的语言风格差异
    """
    if not character_style_analyzer:
        raise HTTPException(status_code=500, detail="Character style analyzer not initialized")
    
    try:
        character_profiles = character_style_analyzer.analyze(request.text)
        
        if request.profile1_name not in character_profiles:
            raise HTTPException(status_code=400, 
                               detail=f"Character '{request.profile1_name}' not found")
        if request.profile2_name not in character_profiles:
            raise HTTPException(status_code=400, 
                               detail=f"Character '{request.profile2_name}' not found")
        
        profile1 = character_profiles[request.profile1_name]
        profile2 = character_profiles[request.profile2_name]
        
        comparison = character_style_analyzer.compare_characters(profile1, profile2)
        
        return JSONResponse(content=comparison)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/perspective/detect")
async def detect_perspective(request: PerspectiveDetectRequest):
    """
    叙事视角自动检测
    检测第一人称/第二人称/第三人称叙事视角
    包含第三人称子类型：全知/有限/客观
    以及叙事时态检测：现在时/过去时
    """
    if not narrative_perspective_detector:
        raise HTTPException(status_code=500, detail="Perspective detector not initialized")
    
    try:
        narrative_text = None
        if request.exclude_dialogue:
            narrative_text = character_style_analyzer.get_narrative_text(request.text)
        
        result = narrative_perspective_detector.detect_perspective(
            request.text, narrative_text)
        
        perspective_cn = {
            'first_person': '第一人称',
            'second_person': '第二人称',
            'third_person_singular': '第三人称单数',
            'third_person_plural': '第三人称复数',
            'third_person_mixed': '第三人称混合',
            'third_person_singular_omniscient': '第三人称单数全知视角',
            'third_person_singular_limited': '第三人称单数有限视角',
            'third_person_singular_objective': '第三人称单数客观视角',
            'third_person_plural_omniscient': '第三人称复数全知视角',
            'third_person_plural_limited': '第三人称复数有限视角',
            'third_person_plural_objective': '第三人称复数客观视角',
            'third_person_mixed_omniscient': '第三人称混合全知视角',
            'third_person_mixed_limited': '第三人称混合有限视角',
            'third_person_mixed_objective': '第三人称混合客观视角',
            'mixed_or_unknown': '混合或未知'
        }
        
        tense_cn = {
            'present': '现在时',
            'past': '过去时'
        }
        
        result['perspective_cn'] = perspective_cn.get(result['perspective'], result['perspective'])
        result['tense_cn'] = tense_cn.get(result['tense'], result['tense'])
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/perspective/info")
async def get_perspective_info():
    """获取视角检测支持的类型说明"""
    return {
        "supported_perspectives": {
            "first_person": "第一人称叙事（使用 I, me, my 等代词）",
            "second_person": "第二人称叙事（使用 you, your 等代词）",
            "third_person_singular": "第三人称单数叙事（使用 he, she, it 等）",
            "third_person_plural": "第三人称复数叙事（使用 they, them 等）",
            "third_person_mixed": "第三人称混合叙事"
        },
        "third_person_subtypes": {
            "omniscient": "全知视角（叙述者知晓所有角色的思想）",
            "limited": "有限视角（聚焦单个角色的思想）",
            "objective": "客观视角（只描述行为，不揭示思想）"
        },
        "supported_tenses": {
            "present": "现在时",
            "past": "过去时"
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
