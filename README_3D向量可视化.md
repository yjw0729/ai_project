# RAG系统3D向量可视化功能

## 🎨 功能概述

系统提供了完整的向量可视化功能，支持将高维向量数据降维到2D/3D空间进行可视化展示，帮助用户直观理解向量数据的分布、聚类和相似性关系。

## 🌟 核心特性

- **多算法支持**: UMAP、T-SNE两种降维算法
- **2D/3D可视化**: 支持平面和立体空间展示
- **业务模块过滤**: 可按业务场景过滤展示数据
- **多种采样策略**: 随机采样、Top-K采样
- **实时渲染**: 支持ECharts-GL、Deck.gl等前端库
- **交互式体验**: 旋转、缩放、悬停详情等

## 📡 API接口详解

### 1. 主要可视化接口

#### 接口信息
- **请求方法**: `GET`
- **请求路径**: `/rag_service/collections/{collection_name}/visualize`
- **功能描述**: 获取指定集合的降维可视化坐标数据

#### Query参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `algo` | string | 否 | `"umap"` | 降维算法: `"umap"` 或 `"tsne"` |
| `n` | int | 否 | `2000` | 样本数量上限，最大10000 |
| `dim` | int | 否 | `2` | 维度: `2` 或 `3` |
| `sample_strategy` | string | 否 | `"random"` | 采样策略: `"random"` 或 `"top_k"` |
| `module` | string | 否 | - | 仅返回指定业务模块的样本 |
| `seed` | int | 否 | - | 随机种子，保证结果可重现 |

#### 成功响应 (200)

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "algo": "umap",
    "dim": 3,
    "n": 1000,
    "coords": [
      {
        "id": 123,
        "case_id": "DOC_001_CHUNK_5",
        "x": -1.234,
        "y": 0.456,
        "z": 0.789,
        "label": "跨境开户",
        "cluster": 2,
        "meta": {
          "doc_id": "d1",
          "chunk_idx": 5,
          "collection": "test_collection"
        }
      }
    ],
    "summary": {
      "total": 1000,
      "collection": "test_collection",
      "sample_strategy": "random",
      "business_module": "cross_border_opening"
    }
  }
}
```

#### 坐标数据字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 内部唯一标识 |
| `case_id` | string | 是 | 业务编号，用于显示 |
| `x` | float | 是 | X轴坐标 |
| `y` | float | 是 | Y轴坐标 |
| `z` | float | 否 | Z轴坐标（dim=3时提供） |
| `label` | string | 否 | 标签（业务模块名），用于着色 |
| `cluster` | int | 否 | 聚类ID |
| `meta` | object | 否 | 元数据对象 |

### 2. 原始向量数据接口

#### 接口信息
- **请求方法**: `GET`
- **请求路径**: `/rag_service/collections/{collection_name}/vectors`
- **功能描述**: 获取原始向量数据（前端自行降维）

#### Query参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | int | 否 | `2000` | 返回向量数量上限，最大5000 |
| `module` | string | 否 | - | 业务模块过滤 |

#### 响应格式

```json
{
  "code": 200,
  "message": "ok",
  "data": [
    {
      "id": 123,
      "case_id": "DOC_001_CHUNK_5",
      "vector": [0.12, 0.34, 0.56, ...],
      "label": "跨境开户",
      "meta": {
        "doc_id": "d1",
        "chunk_idx": 5
      }
    }
  ]
}
```

### 3. 异步可视化任务接口

#### 创建任务
- **请求方法**: `POST`
- **请求路径**: `/rag_service/visualize/jobs`
- **Content-Type**: `application/json`

**请求体**:
```json
{
  "collection": "test_collection",
  "algo": "umap",
  "n": 5000,
  "dim": 3,
  "sample_strategy": "random",
  "module": "cross_border_opening"
}
```

**响应**:
```json
{
  "code": 501,
  "message": "异步可视化任务暂未实现，请使用同步接口",
  "data": null
}
```

#### 查询任务状态
- **请求方法**: `GET`
- **请求路径**: `/rag_service/visualize/jobs/{job_id}`

目前返回501，表示暂未实现异步处理。

## 🎯 前端集成指南

### 1. 获取可视化数据

```javascript
// 3D UMAP可视化
async function getVisualizationData(collectionName, options = {}) {
  const params = new URLSearchParams({
    algo: options.algo || 'umap',
    n: options.n || 1000,
    dim: options.dim || 3,
    sample_strategy: options.sampleStrategy || 'random',
    module: options.businessModule || '',
    seed: options.seed || ''
  });

  const response = await fetch(`/rag_service/collections/${collectionName}/visualize?${params}`);
  const data = await response.json();

  if (data.code === 200) {
    return data.data;
  } else {
    throw new Error(data.message);
  }
}

// 使用示例
const visData = await getVisualizationData('documents', {
  algo: 'tsne',
  n: 2000,
  dim: 3,
  businessModule: 'cross_border_opening'
});

console.log(visData.coords.length); // 坐标点数量
console.log(visData.coords[0]); // 第一个点的详细信息
```

### 2. ECharts-GL 3D散点图

```javascript
// 准备数据
function prepareScatter3DData(coords) {
  return coords.map(coord => ({
    value: [coord.x, coord.y, coord.z],
    itemStyle: {
      color: getColorByLabel(coord.label)
    },
    name: coord.case_id,
    meta: coord.meta
  }));
}

// 根据标签获取颜色
function getColorByLabel(label) {
  const colorMap = {
    '跨境开户': '#FF6B6B',
    '跨境交易': '#4ECDC4',
    '互联网开户': '#45B7D1',
    '互联网交易': '#96CEB4'
  };
  return colorMap[label] || '#CCCCCC';
}

// ECharts配置
function create3DScatterOption(visData) {
  const data = prepareScatter3DData(visData.coords);

  return {
    title: {
      text: `${visData.algo.toUpperCase()} ${visData.dim}D 可视化`,
      subtext: `样本数: ${visData.n}, 集合: ${visData.summary.collection}`
    },
    tooltip: {
      formatter: function(params) {
        const coord = visData.coords[params.dataIndex];
        return `
          <b>${coord.case_id}</b><br/>
          标签: ${coord.label}<br/>
          聚类: ${coord.cluster}<br/>
          文档: ${coord.meta.doc_id}<br/>
          块索引: ${coord.meta.chunk_idx}
        `;
      }
    },
    xAxis3D: {
      name: 'X',
      type: 'value'
    },
    yAxis3D: {
      name: 'Y',
      type: 'value'
    },
    zAxis3D: {
      name: 'Z',
      type: 'value'
    },
    grid3D: {
      viewControl: {
        projection: 'orthographic'
      }
    },
    series: [{
      name: '向量分布',
      type: 'scatter3D',
      data: data,
      symbolSize: 6,
      itemStyle: {
        opacity: 0.8
      },
      emphasis: {
        itemStyle: {
          opacity: 1
        }
      }
    }]
  };
}

// 初始化图表
const chart = echarts.init(document.getElementById('chart-container'), 'dark');
const option = create3DScatterOption(visData);
chart.setOption(option);

// 添加交互事件
chart.on('click', function(params) {
  const coord = visData.coords[params.dataIndex];
  console.log('点击了点:', coord);
  // 可以在这里显示详细信息或跳转到相关文档
});
```

### 3. Deck.gl 3D可视化

```javascript
import {ScatterplotLayer} from '@deck.gl/layers';
import {Deck} from '@deck.gl/core';

// 准备Deck.gl数据
function prepareDeckData(coords) {
  return coords.map(coord => ({
    position: [coord.x, coord.y, coord.z || 0],
    color: getColorByLabel(coord.label),
    radius: 5,
    info: coord
  }));
}

// 创建图层
const scatterLayer = new ScatterplotLayer({
  id: 'vector-scatter',
  data: prepareDeckData(visData.coords),
  getPosition: d => d.position,
  getColor: d => d.color,
  getRadius: d => d.radius,
  pickable: true,
  onClick: ({object}) => {
    if (object) {
      console.log('点击了向量点:', object.info);
    }
  }
});

// 创建Deck实例
const deck = new Deck({
  canvas: 'deck-canvas',
  width: '100%',
  height: '100%',
  initialViewState: {
    longitude: 0,
    latitude: 0,
    zoom: 1,
    pitch: 45,
    bearing: 0
  },
  controller: true,
  layers: [scatterLayer]
});
```

### 4. 动态更新和过滤

```javascript
// 业务模块切换
async function switchBusinessModule(module) {
  const visData = await getVisualizationData('documents', {
    businessModule: module,
    dim: 3,
    n: 1000
  });

  // 更新图表
  const newOption = create3DScatterOption(visData);
  chart.setOption(newOption, true); // 不合并，完全替换
}

// 算法切换
async function switchAlgorithm(algo) {
  const visData = await getVisualizationData('documents', {
    algo: algo,
    dim: 3,
    n: 1000
  });

  const newOption = create3DScatterOption(visData);
  chart.setOption(newOption, true);
}

// 监听用户操作
document.getElementById('module-select').addEventListener('change', (e) => {
  switchBusinessModule(e.target.value);
});

document.getElementById('algo-select').addEventListener('change', (e) => {
  switchAlgorithm(e.target.value);
});
```

### 5. 性能优化

```javascript
// 防抖处理频繁请求
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 缓存可视化数据
const visCache = new Map();

async function getCachedVisualization(collectionName, options) {
  const cacheKey = JSON.stringify({collectionName, ...options});

  if (visCache.has(cacheKey)) {
    return visCache.get(cacheKey);
  }

  const data = await getVisualizationData(collectionName, options);
  visCache.set(cacheKey, data);

  // 限制缓存大小
  if (visCache.size > 10) {
    const firstKey = visCache.keys().next().value;
    visCache.delete(firstKey);
  }

  return data;
}

// 使用防抖的更新函数
const debouncedUpdate = debounce(async () => {
  const visData = await getCachedVisualization('documents', currentOptions);
  updateChart(visData);
}, 300);
```

## 🧪 测试验证

运行可视化API测试：

```bash
python deploy/test_visualization_api.py
```

测试内容包括：
- ✅ 2D/3D降维算法测试
- ✅ 不同采样策略验证
- ✅ 业务模块过滤测试
- ✅ 参数验证检查
- ✅ 原始向量数据获取

## ⚠️ 注意事项

### 性能考虑
- **样本数量**: n≤10000，建议生产环境5000以内
- **降维耗时**: UMAP比T-SNE快，适合实时交互
- **内存使用**: 大数据集需要注意浏览器内存限制

### 数据安全
- **敏感信息**: 向量坐标本身不包含原始文本，但meta信息可能需要脱敏
- **访问控制**: 建议在生产环境添加用户权限验证

### 浏览器兼容性
- **WebGL支持**: 3D可视化需要WebGL支持
- **内存限制**: 大数据集可能导致浏览器内存不足

## 🎨 可视化效果展示

### 3D散点图示例

```
📊 UMAP 3D 可视化
├── 🔴 跨境开户 - 红色聚类
├── 🔵 跨境交易 - 蓝色聚类
├── 🟢 互联网开户 - 绿色聚类
└── 🟡 互联网交易 - 黄色聚类
```

### 交互功能

- **旋转查看**: 360°观察向量分布
- **缩放探索**: 放大查看聚类细节
- **悬停详情**: 显示文档和块信息
- **点击跳转**: 跳转到相关文档内容
- **筛选过滤**: 按业务模块动态过滤

## 🚀 高级用法

### 1. 自定义配色方案

```javascript
const customColorScheme = {
  '跨境开户': '#FF6B6B',
  '跨境交易': '#4ECDC4',
  '互联网开户': '#45B7D1',
  '互联网交易': '#96CEB4',
  '其他': '#CCCCCC'
};
```

### 2. 聚类分析集成

```javascript
// 结合后端的聚类信息进行高级分析
function analyzeClusters(coords) {
  const clusters = {};
  coords.forEach(coord => {
    const clusterId = coord.cluster;
    if (!clusters[clusterId]) {
      clusters[clusterId] = [];
    }
    clusters[clusterId].push(coord);
  });

  // 分析每个聚类的特征
  Object.keys(clusters).forEach(clusterId => {
    const clusterCoords = clusters[clusterId];
    console.log(`聚类 ${clusterId}: ${clusterCoords.length} 个点`);
  });
}
```

### 3. 时间序列可视化

```javascript
// 如果有时间信息，可以制作4D可视化（空间+时间）
function addTimeDimension(coords, timeField) {
  return coords.map(coord => ({
    ...coord,
    time: coord.meta[timeField] || 0
  }));
}
```

现在前端可以轻松集成强大的3D向量可视化功能，为用户提供沉浸式的向量空间探索体验！🚀✨
