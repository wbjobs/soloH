<template>
  <div class="app-container">
    <h1 class="main-title">平面光栅光谱仪模拟器</h1>
    
    <div class="main-layout">
      <div class="control-panel">
        <div class="panel-section">
          <h3>仪器参数</h3>
          
          <div class="param-item">
            <label>入射角 θᵢ (度)</label>
            <input type="range" v-model.number="params.incidentAngle" 
                   min="0" max="60" step="0.1" />
            <span class="param-value">{{ params.incidentAngle.toFixed(1) }}°</span>
          </div>
          
          <div class="param-item">
            <label>光栅常数 d (μm)</label>
            <input type="range" v-model.number="params.gratingConstant" 
                   min="0.5" max="5" step="0.01" />
            <span class="param-value">{{ params.gratingConstant.toFixed(2) }} μm</span>
          </div>
          
          <div class="param-item">
            <label>焦距 f (mm)</label>
            <input type="range" v-model.number="params.focalLength" 
                   min="30" max="500" step="1" />
            <span class="param-value">{{ params.focalLength }} mm</span>
          </div>
          
          <div class="param-item">
            <label>像素尺寸 (μm)</label>
            <input type="range" v-model.number="params.pixelSize" 
                   min="5" max="25" step="0.5" />
            <span class="param-value">{{ params.pixelSize.toFixed(1) }} μm</span>
          </div>
          
          <div class="param-item">
            <label>衍射级次 m</label>
            <select v-model.number="params.order">
              <option :value="-3">-3 级</option>
              <option :value="-2">-2 级</option>
              <option :value="-1">-1 级</option>
              <option :value="1">1 级</option>
              <option :value="2">2 级</option>
              <option :value="3">3 级</option>
            </select>
          </div>
        </div>

        <div class="panel-section">
          <h3>狭缝函数</h3>
          <div class="param-item">
            <label>狭缝类型</label>
            <select v-model="slit.type">
              <option value="none">无（理想狭缝）</option>
              <option value="rectangle">矩形狭缝</option>
              <option value="triangle">三角形狭缝</option>
              <option value="gaussian">高斯狭缝</option>
            </select>
          </div>
          <div class="param-item">
            <label>狭缝宽度 (像素)</label>
            <input type="range" v-model.number="slit.width" 
                   min="1" max="30" step="0.5" />
            <span class="param-value">{{ slit.width.toFixed(1) }} px</span>
          </div>
          <div class="param-item">
            <label>
              <input type="checkbox" v-model="correction.enableSecondOrderSubtraction" />
              自动扣除二阶衍射干扰
            </label>
          </div>
        </div>

        <div class="panel-section">
          <h3>光源类型</h3>
          <div class="param-item">
            <label>光源</label>
            <select v-model="source.type">
              <option value="mercury">汞灯 (离散谱线)</option>
              <option value="blackbody">黑体辐射 (连续谱)</option>
            </select>
          </div>
          <template v-if="source.type === 'blackbody'">
            <div class="param-item">
              <label>黑体温度 T (K)</label>
              <input type="range" v-model.number="source.temperature" 
                     min="2000" max="10000" step="50" />
              <span class="param-value">{{ source.temperature }} K</span>
            </div>
            <div class="param-item">
              <label>
                <input type="checkbox" v-model="source.enableFit" />
                启用温度拟合
              </label>
            </div>
            <div v-if="source.fittedTemperature" class="fit-result">
              <p>拟合温度: {{ source.fittedTemperature.toFixed(0) }} K</p>
              <p>拟合误差: {{ source.fitError.toFixed(2) }}%</p>
            </div>
            <button class="btn-fit" @click="fitBlackbodyTemperature">
              拟合黑体温度
            </button>
          </template>
        </div>
        
        <div class="panel-section">
          <h3>噪声模拟</h3>
          
          <div class="param-item">
            <label>高斯噪声 σ</label>
            <input type="range" v-model.number="noise.gaussian" 
                   min="0" max="100" step="1" />
            <span class="param-value">{{ noise.gaussian }}</span>
          </div>
          
          <div class="param-item">
            <label>散粒噪声系数</label>
            <input type="range" v-model.number="noise.shot" 
                   min="0" max="1" step="0.01" />
            <span class="param-value">{{ noise.shot.toFixed(2) }}</span>
          </div>
          
          <button class="btn-regenerate" @click="regenerateNoise">
            重新生成噪声
          </button>
        </div>
        
        <div class="panel-section">
          <h3>校准功能</h3>
          <div class="calibration-info">
            <p>点击光谱图上的谱峰选择校准点</p>
            <p v-if="calibrationPoints.length > 0">
              已选校准点: {{ calibrationPoints.length }} 个
            </p>
            <div v-if="calibrationCoeffs" class="calibration-result">
              <p>校准系数:</p>
              <p v-for="(c, i) in calibrationCoeffs" :key="i">
                a{{ i }} = {{ c.toExponential(4) }}
              </p>
            </div>
          </div>
          <div class="calibration-buttons">
            <button @click="performCalibration" 
                    :disabled="calibrationPoints.length < 2">
              执行校准
            </button>
            <button @click="clearCalibration">
              清除校准
            </button>
            <button @click="toggleCalibrationMode">
              {{ calibrationMode ? '退出校准模式' : '校准模式' }}
            </button>
          </div>
        </div>
        
        <div class="panel-section">
          <h3>显示选项</h3>
          <div class="checkbox-item">
            <label>
              <input type="checkbox" v-model="display.showWavelengthScale" />
              显示波长刻度
            </label>
          </div>
          <div class="checkbox-item">
            <label>
              <input type="checkbox" v-model="display.showPixelScale" />
              显示像素刻度
            </label>
          </div>
          <div class="checkbox-item">
            <label>
              <input type="checkbox" v-model="display.showSpectrumLines" />
              显示谱线标注
            </label>
          </div>
          <div class="checkbox-item">
            <label>
              <input type="checkbox" v-model="display.showCorrectedSpectrum" />
              显示校正后光谱
            </label>
          </div>
        </div>
      </div>
      
      <div class="canvas-container">
        <canvas 
          ref="spectrumCanvas" 
          :width="canvasWidth" 
          :height="canvasHeight"
          @click="handleCanvasClick"
          @mousemove="handleMouseMove">
        </canvas>
        
        <div v-if="mousePos" class="mouse-info">
          像素: {{ mousePos.pixel }} | 
          波长: {{ mousePos.wavelength.toFixed(2) }} nm
        </div>
        
        <div class="spectrum-info">
          <h3>{{ source.type === 'mercury' ? '汞灯特征谱线' : '黑体辐射参数' }}</h3>
          <div v-if="source.type === 'mercury'" class="spectrum-lines">
            <span 
              v-for="line in mercuryLines" 
              :key="line.wavelength"
              class="spectrum-line-tag"
              :style="{ background: line.color }">
              {{ line.wavelength }} nm
            </span>
          </div>
          <div v-else class="blackbody-info">
            <p>维恩位移: λ_max = {{ (2897.77 / source.temperature).toFixed(1) }} nm</p>
            <p>总辐射出射度: M = {{ (5.67e-8 * source.temperature ** 4).toExponential(3) }} W/m²</p>
          </div>
        </div>
      </div>
    </div>
    
    <div class="info-panel">
      <h3>光栅方程</h3>
      <p>d(sinθᵢ + sinθ_d) = mλ</p>
      <div class="equation-params">
        <span>d = {{ params.gratingConstant }} μm</span>
        <span>θᵢ = {{ params.incidentAngle }}°</span>
        <span>m = {{ params.order }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'

const canvasWidth = 1000
const canvasHeight = 400
const spectrumCanvas = ref(null)

const mousePos = ref(null)

const params = reactive({
  incidentAngle: 15,
  gratingConstant: 1.67,
  focalLength: 100,
  pixelSize: 15,
  order: 1
})

const slit = reactive({
  type: 'gaussian',
  width: 3
})

const source = reactive({
  type: 'mercury',
  temperature: 5000,
  fittedTemperature: null,
  fitError: null,
  enableFit: false
})

const correction = reactive({
  enableSecondOrderSubtraction: false
})

const noise = reactive({
  gaussian: 10,
  shot: 0.1
})

const display = reactive({
  showWavelengthScale: true,
  showPixelScale: true,
  showSpectrumLines: true,
  showCorrectedSpectrum: false
})

const calibrationMode = ref(false)
const calibrationPoints = ref([])
const calibrationCoeffs = ref(null)

const mercuryLines = [
  { wavelength: 365.0, intensity: 0.5, color: '#8B00FF', name: 'U' },
  { wavelength: 404.7, intensity: 0.8, color: '#7B68EE', name: 'V' },
  { wavelength: 435.8, intensity: 1.0, color: '#00BFFF', name: 'H' },
  { wavelength: 546.1, intensity: 1.0, color: '#00FF00', name: 'E' },
  { wavelength: 577.0, intensity: 0.6, color: '#FFD700', name: 'D1' },
  { wavelength: 579.1, intensity: 0.5, color: '#FFA500', name: 'D2' }
]

const centerDataPixel = (canvasWidth - 80) / 2

const wavelengthToPixel = (wavelength) => {
  return wavelengthToPixelForOrder(wavelength, params.order)
}

const wavelengthToPixelForOrder = (wavelength, order) => {
  const d = params.gratingConstant * 1e-6
  const theta_i = params.incidentAngle * Math.PI / 180
  const lambda = wavelength * 1e-9

  if (order === 0) return null

  const sin_theta_d = (order * lambda / d) - Math.sin(theta_i)

  if (Math.abs(sin_theta_d) > 1) return null

  const theta_d = Math.asin(sin_theta_d)
  const x = params.focalLength * Math.tan(theta_d)
  const pixel = x / (params.pixelSize * 1e-3) + centerDataPixel

  return pixel
}

const pixelToWavelength = (pixel) => {
  const d = params.gratingConstant * 1e-6
  const theta_i = params.incidentAngle * Math.PI / 180
  const m = params.order

  if (m === 0) return null

  const x = (pixel - centerDataPixel) * params.pixelSize * 1e-3
  const theta_d = Math.atan(x / params.focalLength)
  const lambda = d * (Math.sin(theta_i) + Math.sin(theta_d)) / m

  return lambda * 1e9
}

const computeFWHMPixels = (wavelength) => {
  const d = params.gratingConstant * 1e-6
  const theta_i = params.incidentAngle * Math.PI / 180
  const m = Math.abs(params.order)

  if (m === 0) return 3

  const lambda = wavelength * 1e-9
  const sin_theta_d = (m * lambda / d) - Math.sin(theta_i)

  if (Math.abs(sin_theta_d) > 1) return 3

  const theta_d = Math.asin(sin_theta_d)
  const cos_theta_d = Math.cos(theta_d)

  const dispersion = (d * cos_theta_d * cos_theta_d * cos_theta_d) / (m * params.focalLength)

  const totalGrooves = 1000
  const resolvingPower = m * totalGrooves
  const fwhmLambda = lambda / resolvingPower

  const fwhmX = fwhmLambda / dispersion

  const fwhmPixels = fwhmX / (params.pixelSize * 1e-3)

  const sigma = fwhmPixels / (2 * Math.sqrt(2 * Math.log(2)))

  return Math.max(sigma, 0.5)
}

const generateSlitKernel = (type, width) => {
  if (type === 'none' || width <= 0) return [1]

  const halfW = Math.ceil(width / 2)
  const kernelSize = halfW * 2 + 1
  const kernel = new Array(kernelSize).fill(0)

  if (type === 'rectangle') {
    for (let i = 0; i < kernelSize; i++) {
      kernel[i] = 1 / kernelSize
    }
  } else if (type === 'triangle') {
    let sum = 0
    for (let i = 0; i < kernelSize; i++) {
      const dist = Math.abs(i - halfW) / halfW
      kernel[i] = 1 - dist
      sum += kernel[i]
    }
    for (let i = 0; i < kernelSize; i++) {
      kernel[i] /= sum
    }
  } else if (type === 'gaussian') {
    const sigma = width / 2.355
    let sum = 0
    for (let i = 0; i < kernelSize; i++) {
      const dist = i - halfW
      kernel[i] = Math.exp(-0.5 * (dist / sigma) ** 2)
      sum += kernel[i]
    }
    for (let i = 0; i < kernelSize; i++) {
      kernel[i] /= sum
    }
  }

  return kernel
}

const convolve = (data, kernel) => {
  const n = data.length
  const k = kernel.length
  const halfK = Math.floor(k / 2)
  const result = new Array(n).fill(0)

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < k; j++) {
      const idx = i - halfK + j
      if (idx >= 0 && idx < n) {
        result[i] += data[idx] * kernel[j]
      }
    }
  }

  return result
}

const planckSpectralRadiance = (wavelengthNm, temperatureK) => {
  const h = 6.626e-34
  const c = 2.998e8
  const k = 1.381e-23
  const lambda = wavelengthNm * 1e-9

  const exponent = h * c / (lambda * k * temperatureK)
  const B = 2 * h * c * c / (lambda ** 5) / (Math.exp(exponent) - 1)

  return B
}

const gaussianRandom = () => {
  let u = 0, v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v)
}

const generateNoisePattern = () => {
  const noiseArray = []
  for (let i = 0; i < canvasWidth; i++) {
    noiseArray.push(gaussianRandom() * noise.gaussian)
  }
  return noiseArray
}

const noisePattern = ref(generateNoisePattern())

const regenerateNoise = () => {
  noisePattern.value = generateNoisePattern()
}

const generateRawSpectrum = () => {
  const plotWidth = canvasWidth - 80
  const data = new Array(plotWidth).fill(0)

  if (source.type === 'mercury') {
    mercuryLines.forEach(line => {
      const pixel = wavelengthToPixel(line.wavelength)
      if (pixel !== null && pixel >= 0 && pixel < plotWidth) {
        const sigma = computeFWHMPixels(line.wavelength)
        const amplitude = line.intensity * 255

        const halfWidth = Math.ceil(8 * sigma)
        const startI = Math.max(0, Math.floor(pixel - halfWidth))
        const endI = Math.min(plotWidth, Math.ceil(pixel + halfWidth))

        for (let i = startI; i < endI; i++) {
          const dist = i - pixel
          const contribution = amplitude * Math.exp(-0.5 * (dist / sigma) ** 2)
          data[i] += contribution
        }
      }
    })
  } else if (source.type === 'blackbody') {
    const wlMin = 200
    const wlMax = 1200
    const nSamples = 400

    for (let s = 0; s < nSamples; s++) {
      const wl = wlMin + (wlMax - wlMin) * s / (nSamples - 1)
      const pixel = wavelengthToPixel(wl)
      if (pixel === null || pixel < 0 || pixel >= plotWidth) continue

      const sigma = Math.max(computeFWHMPixels(wl), 1.0)
      const radiance = planckSpectralRadiance(wl, source.temperature)

      const halfWidth = Math.ceil(6 * sigma)
      const startI = Math.max(0, Math.floor(pixel - halfWidth))
      const endI = Math.min(plotWidth, Math.ceil(pixel + halfWidth))

      for (let i = startI; i < endI; i++) {
        const dist = i - pixel
        data[i] += radiance * Math.exp(-0.5 * (dist / sigma) ** 2)
      }
    }

    const maxVal = Math.max(...data, 1e-30)
    for (let i = 0; i < plotWidth; i++) {
      data[i] = (data[i] / maxVal) * 255
    }
  }

  return data
}

const computeSecondOrderContribution = (rawData) => {
  if (!correction.enableSecondOrderSubtraction) return null
  if (Math.abs(params.order) !== 1) return null

  const plotWidth = canvasWidth - 80
  const secondOrder = params.order * 2
  const contamination = new Array(plotWidth).fill(0)

  if (source.type === 'mercury') {
    mercuryLines.forEach(line => {
      const pixelM2 = wavelengthToPixelForOrder(line.wavelength, secondOrder)
      if (pixelM2 === null || pixelM2 < 0 || pixelM2 >= plotWidth) return

      const sigmaM1 = computeFWHMPixels(line.wavelength * 2)
      const sigmaM2 = computeFWHMPixels(line.wavelength)
      const effectiveSigma = Math.sqrt(sigmaM1 * sigmaM1 + sigmaM2 * sigmaM2)
      const amplitude = line.intensity * 255 * 0.3

      const halfWidth = Math.ceil(8 * effectiveSigma)
      const startI = Math.max(0, Math.floor(pixelM2 - halfWidth))
      const endI = Math.min(plotWidth, Math.ceil(pixelM2 + halfWidth))

      for (let i = startI; i < endI; i++) {
        const dist = i - pixelM2
        contamination[i] += amplitude * Math.exp(-0.5 * (dist / effectiveSigma) ** 2)
      }
    })
  } else if (source.type === 'blackbody') {
    const wlMin = 200
    const wlMax = 600
    const nSamples = 200

    for (let s = 0; s < nSamples; s++) {
      const wlM2 = wlMin + (wlMax - wlMin) * s / (nSamples - 1)
      const pixelM2 = wavelengthToPixelForOrder(wlM2, secondOrder)
      if (pixelM2 === null || pixelM2 < 0 || pixelM2 >= plotWidth) continue

      const sigmaM2 = computeFWHMPixels(wlM2)
      const radianceM2 = planckSpectralRadiance(wlM2, source.temperature)

      const halfWidth = Math.ceil(6 * sigmaM2)
      const startI = Math.max(0, Math.floor(pixelM2 - halfWidth))
      const endI = Math.min(plotWidth, Math.ceil(pixelM2 + halfWidth))

      for (let i = startI; i < endI; i++) {
        const dist = i - pixelM2
        contamination[i] += radianceM2 * Math.exp(-0.5 * (dist / sigmaM2) ** 2)
      }
    }

    const maxRaw = Math.max(...rawData, 1e-30)
    for (let i = 0; i < plotWidth; i++) {
      contamination[i] = (contamination[i] / maxRaw) * 255 * 0.15
    }
  }

  return contamination
}

const correctedSpectrumData = computed(() => {
  let data = generateRawSpectrum()

  if (slit.type !== 'none') {
    const kernel = generateSlitKernel(slit.type, slit.width)
    data = convolve(data, kernel)
  }

  const secondOrder = computeSecondOrderContribution(data)
  if (secondOrder) {
    for (let i = 0; i < data.length; i++) {
      data[i] = Math.max(0, data[i] - secondOrder[i])
    }
  }

  const plotWidth = canvasWidth - 80

  const maxVal = Math.max(...data, 1)
  if (maxVal > 1023) {
    for (let i = 0; i < plotWidth; i++) {
      data[i] = Math.min(data[i], 1023)
    }
  }

  for (let i = 0; i < plotWidth; i++) {
    const shotNoise = noise.shot > 0 && data[i] > 0
      ? gaussianRandom() * Math.sqrt(Math.abs(data[i])) * noise.shot
      : 0
    data[i] = Math.max(0, Math.min(1023, data[i] + noisePattern.value[i] + shotNoise))
  }

  return data
})

const fitBlackbodyTemperature = () => {
  const plotWidth = canvasWidth - 80
  const data = correctedSpectrumData.value

  const wlPixels = []
  const wlStart = 350
  const wlEnd = 800
  const step = 5

  for (let wl = wlStart; wl <= wlEnd; wl += step) {
    const p = wavelengthToPixel(wl)
    if (p !== null && p >= 0 && p < plotWidth) {
      const idx = Math.floor(p)
      const intensity = data[idx] || 0
      if (intensity > 0) {
        wlPixels.push({ wavelength: wl, intensity, pixel: p })
      }
    }
  }

  if (wlPixels.length < 5) {
    source.fittedTemperature = null
    source.fitError = null
    return
  }

  let bestT = 3000
  let bestError = Infinity

  for (let T = 2500; T <= 10000; T += 50) {
    let sumSqError = 0
    let sumSqData = 0

    for (const pt of wlPixels) {
      const B = planckSpectralRadiance(pt.wavelength, T)
      sumSqError += (pt.intensity - B * 1e-14) ** 2
      sumSqData += pt.intensity ** 2
    }

    const relativeError = Math.sqrt(sumSqError / sumSqData) * 100
    if (relativeError < bestError) {
      bestError = relativeError
      bestT = T
    }
  }

  for (let subT = bestT - 40; subT <= bestT + 40; subT += 10) {
    if (subT < 2500 || subT > 10000) continue
    let sumSqError = 0
    let sumSqData = 0

    for (const pt of wlPixels) {
      const B = planckSpectralRadiance(pt.wavelength, subT)
      sumSqError += (pt.intensity - B * 1e-14) ** 2
      sumSqData += pt.intensity ** 2
    }

    const relativeError = Math.sqrt(sumSqError / sumSqData) * 100
    if (relativeError < bestError) {
      bestError = relativeError
      bestT = subT
    }
  }

  source.fittedTemperature = bestT
  source.fitError = bestError
}

const findNearestPeak = (clickPixel) => {
  const plotWidth = canvasWidth - 80
  const searchRadius = 30
  const startI = Math.max(0, clickPixel - searchRadius)
  const endI = Math.min(plotWidth, clickPixel + searchRadius)

  let peakPixel = clickPixel
  let peakValue = 0
  let found = false

  for (let i = startI; i < endI; i++) {
    const val = correctedSpectrumData.value[i] || 0
    const prevVal = i > 0 ? (correctedSpectrumData.value[i - 1] || 0) : 0
    const nextVal = i < plotWidth - 1 ? (correctedSpectrumData.value[i + 1] || 0) : 0

    if (val > prevVal && val > nextVal && val > peakValue) {
      peakValue = val
      peakPixel = i
      found = true
    }
  }

  if (!found) return null

  const maxIntensity = Math.max(...correctedSpectrumData.value.slice(0, plotWidth), 1)
  const threshold = maxIntensity * 0.15
  if (peakValue < threshold) return null

  return peakPixel
}

const drawSpectrum = () => {
  const canvas = spectrumCanvas.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  const margin = { top: 30, right: 30, bottom: 60, left: 50 }
  const width = canvasWidth - margin.left - margin.right
  const height = canvasHeight - margin.top - margin.bottom

  ctx.fillStyle = '#0a0e27'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  const plotWidth = canvasWidth - 80
  const maxIntensity = Math.max(...correctedSpectrumData.value.slice(0, plotWidth), 1)

  ctx.beginPath()
  ctx.strokeStyle = '#00BFFF'
  ctx.lineWidth = 1

  for (let i = 0; i < width; i++) {
    const x = margin.left + i
    const intensity = correctedSpectrumData.value[i] || 0
    const y = margin.top + height - (intensity / maxIntensity) * height

    if (i === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
  }
  ctx.stroke()

  ctx.beginPath()
  for (let i = 0; i < width; i++) {
    const x = margin.left + i
    const intensity = correctedSpectrumData.value[i] || 0
    const y = margin.top + height - (intensity / maxIntensity) * height
    ctx.lineTo(x, margin.top + height)
  }
  ctx.closePath()
  ctx.fillStyle = '#00BFFF10'
  ctx.fill()

  if (correction.enableSecondOrderSubtraction && Math.abs(params.order) === 1) {
    const rawData = generateRawSpectrum()
    const contamination = computeSecondOrderContribution(rawData)
    if (contamination) {
      ctx.beginPath()
      ctx.strokeStyle = '#FF444480'
      ctx.lineWidth = 1
      ctx.setLineDash([3, 3])
      for (let i = 0; i < width; i++) {
        const x = margin.left + i
        const intensity = contamination[i] || 0
        const y = margin.top + height - (intensity / maxIntensity) * height
        if (i === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      }
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  if (display.showCorrectedSpectrum && correction.enableSecondOrderSubtraction && Math.abs(params.order) === 1) {
    const rawData = generateRawSpectrum()
    let uncorrected = [...rawData]
    if (slit.type !== 'none') {
      const kernel = generateSlitKernel(slit.type, slit.width)
      uncorrected = convolve(uncorrected, kernel)
    }
    ctx.beginPath()
    ctx.strokeStyle = '#88888850'
    ctx.lineWidth = 1
    for (let i = 0; i < width; i++) {
      const x = margin.left + i
      const intensity = uncorrected[i] || 0
      const y = margin.top + height - (intensity / maxIntensity) * height
      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    }
    ctx.stroke()
  }

  ctx.strokeStyle = '#666'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(margin.left, margin.top)
  ctx.lineTo(margin.left, margin.top + height)
  ctx.lineTo(margin.left + width, margin.top + height)
  ctx.stroke()

  if (display.showWavelengthScale) {
    ctx.fillStyle = '#aaa'
    ctx.font = '12px Arial'
    ctx.textAlign = 'center'

    for (let wl = 350; wl <= 700; wl += 50) {
      const pixel = wavelengthToPixel(wl)
      if (pixel !== null && pixel >= 0 && pixel < width) {
        const x = margin.left + pixel
        ctx.beginPath()
        ctx.moveTo(x, margin.top + height)
        ctx.lineTo(x, margin.top + height + 5)
        ctx.stroke()
        ctx.fillText(wl + ' nm', x, margin.top + height + 20)
      }
    }
  }

  if (display.showPixelScale) {
    ctx.fillStyle = '#888'
    ctx.font = '10px Arial'
    ctx.textAlign = 'center'

    for (let p = 0; p < width; p += 100) {
      const x = margin.left + p
      ctx.beginPath()
      ctx.moveTo(x, margin.top + height + 35)
      ctx.lineTo(x, margin.top + height + 40)
      ctx.stroke()
      ctx.fillText(p.toString(), x, margin.top + height + 52)
    }
  }

  if (display.showSpectrumLines && source.type === 'mercury') {
    mercuryLines.forEach(line => {
      const pixel = wavelengthToPixel(line.wavelength)
      if (pixel !== null && pixel >= 0 && pixel < width) {
        const x = margin.left + pixel

        ctx.strokeStyle = line.color
        ctx.setLineDash([5, 5])
        ctx.beginPath()
        ctx.moveTo(x, margin.top)
        ctx.lineTo(x, margin.top + height)
        ctx.stroke()
        ctx.setLineDash([])

        ctx.fillStyle = line.color
        ctx.font = 'bold 11px Arial'
        ctx.textAlign = 'center'
        ctx.fillText(line.wavelength + ' nm', x, margin.top - 10)
      }
    })
  }

  if (display.showSpectrumLines && source.type === 'blackbody') {
    const peakWl = 2897.77 / source.temperature
    const pixel = wavelengthToPixel(peakWl)
    if (pixel !== null && pixel >= 0 && pixel < width) {
      const x = margin.left + pixel
      ctx.strokeStyle = '#FF6600'
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      ctx.moveTo(x, margin.top)
      ctx.lineTo(x, margin.top + height)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = '#FF6600'
      ctx.font = 'bold 11px Arial'
      ctx.textAlign = 'center'
      ctx.fillText('λ_max = ' + peakWl.toFixed(1) + ' nm', x, margin.top - 10)
    }
  }

  calibrationPoints.value.forEach((point, index) => {
    const x = margin.left + point.pixel
    ctx.beginPath()
    ctx.arc(x, margin.top + height - 30, 8, 0, Math.PI * 2)
    ctx.fillStyle = '#FFD700'
    ctx.fill()
    ctx.strokeStyle = '#FFF'
    ctx.lineWidth = 2
    ctx.stroke()

    ctx.fillStyle = '#000'
    ctx.font = 'bold 10px Arial'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText((index + 1).toString(), x, margin.top + height - 30)
  })

  ctx.fillStyle = '#aaa'
  ctx.font = '14px Arial'
  ctx.textAlign = 'center'
  ctx.fillText('波长 (nm)', margin.left + width / 2, canvasHeight - 5)

  ctx.save()
  ctx.translate(15, margin.top + height / 2)
  ctx.rotate(-Math.PI / 2)
  ctx.fillText('强度', 0, 0)
  ctx.restore()
}

const handleCanvasClick = (event) => {
  if (!calibrationMode.value) return

  const rect = spectrumCanvas.value.getBoundingClientRect()
  const scaleX = canvasWidth / rect.width
  const pixel = Math.floor((event.clientX - rect.left) * scaleX)

  const margin = 50
  const dataPixel = pixel - margin

  if (dataPixel < 0 || dataPixel >= canvasWidth - 80) return

  const peakPixel = findNearestPeak(dataPixel)
  if (peakPixel === null) return

  const wavelength = pixelToWavelength(peakPixel)
  if (wavelength === null || wavelength < 0) return

  const existingIndex = calibrationPoints.value.findIndex(
    p => Math.abs(p.pixel - peakPixel) < 10
  )

  if (existingIndex >= 0) {
    calibrationPoints.value.splice(existingIndex, 1)
  } else {
    calibrationPoints.value.push({
      pixel: peakPixel,
      wavelength: wavelength
    })
  }
}

const handleMouseMove = (event) => {
  const rect = spectrumCanvas.value.getBoundingClientRect()
  const scaleX = canvasWidth / rect.width
  const pixel = Math.floor((event.clientX - rect.left) * scaleX)

  const margin = 50
  const dataPixel = pixel - margin

  if (dataPixel >= 0 && dataPixel < canvasWidth - 80) {
    const wavelength = pixelToWavelength(dataPixel)
    if (wavelength !== null && wavelength > 0) {
      mousePos.value = {
        pixel: dataPixel,
        wavelength: wavelength
      }
    } else {
      mousePos.value = null
    }
  } else {
    mousePos.value = null
  }
}

const toggleCalibrationMode = () => {
  calibrationMode.value = !calibrationMode.value
  if (!calibrationMode.value) {
    calibrationPoints.value = []
  }
}

const performCalibration = () => {
  if (calibrationPoints.value.length < 2) return

  const n = calibrationPoints.value.length
  const degree = Math.min(n - 1, 3)

  const matrix = []
  for (let i = 0; i < n; i++) {
    const row = []
    for (let j = 0; j <= degree; j++) {
      row.push(Math.pow(calibrationPoints.value[i].pixel, j))
    }
    row.push(calibrationPoints.value[i].wavelength)
    matrix.push(row)
  }

  for (let col = 0; col <= degree; col++) {
    let maxRow = col
    for (let row = col + 1; row < n; row++) {
      if (Math.abs(matrix[row][col]) > Math.abs(matrix[maxRow][col])) {
        maxRow = row
      }
    }

    if (Math.abs(matrix[maxRow][col]) < 1e-10) continue

    [matrix[col], matrix[maxRow]] = [matrix[maxRow], matrix[col]]

    for (let row = col + 1; row < n; row++) {
      const factor = matrix[row][col] / matrix[col][col]
      for (let j = col; j <= degree + 1; j++) {
        matrix[row][j] -= factor * matrix[col][j]
      }
    }
  }

  const coeffs = new Array(degree + 1).fill(0)
  for (let row = degree; row >= 0; row--) {
    let sum = matrix[row][degree + 1]
    for (let j = row + 1; j <= degree; j++) {
      sum -= matrix[row][j] * coeffs[j]
    }
    if (Math.abs(matrix[row][row]) > 1e-10) {
      coeffs[row] = sum / matrix[row][row]
    }
  }

  calibrationCoeffs.value = coeffs
}

const clearCalibration = () => {
  calibrationPoints.value = []
  calibrationCoeffs.value = null
}

watch([params, noise, display, calibrationPoints, slit, source, correction], () => {
  nextTick(() => {
    drawSpectrum()
  })
}, { deep: true })

onMounted(() => {
  drawSpectrum()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.main-title {
  text-align: center;
  font-size: 28px;
  color: #00BFFF;
  text-shadow: 0 0 10px rgba(0, 191, 255, 0.5);
  margin-bottom: 10px;
}

.main-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.control-panel {
  width: 340px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  padding-right: 5px;
}

.control-panel::-webkit-scrollbar {
  width: 6px;
}

.control-panel::-webkit-scrollbar-track {
  background: #0a0e27;
}

.control-panel::-webkit-scrollbar-thumb {
  background: #2a3050;
  border-radius: 3px;
}

.panel-section {
  background: linear-gradient(135deg, #1a1f3a 0%, #0d1229 100%);
  border-radius: 12px;
  padding: 15px;
  border: 1px solid #2a3050;
}

.panel-section h3 {
  color: #00BFFF;
  font-size: 16px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2a3050;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
}

.param-item label {
  font-size: 13px;
  color: #aaa;
}

.param-item input[type="range"] {
  width: 100%;
  accent-color: #00BFFF;
}

.param-item select {
  padding: 6px 10px;
  background: #0a0e27;
  border: 1px solid #2a3050;
  color: #e0e0e0;
  border-radius: 6px;
  font-size: 13px;
}

.param-value {
  font-size: 12px;
  color: #00BFFF;
  text-align: right;
}

.btn-regenerate {
  width: 100%;
  padding: 8px;
  background: linear-gradient(135deg, #00BFFF 0%, #0080FF 100%);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-regenerate:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(0, 191, 255, 0.4);
}

.btn-fit {
  width: 100%;
  padding: 8px;
  background: linear-gradient(135deg, #FF6600 0%, #CC4400 100%);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 8px;
}

.btn-fit:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(255, 102, 0, 0.4);
}

.fit-result {
  margin-top: 10px;
  padding: 8px;
  background: rgba(255, 102, 0, 0.1);
  border-radius: 6px;
}

.fit-result p {
  font-size: 11px;
  color: #FF9944;
}

.calibration-info {
  font-size: 12px;
  color: #888;
  margin-bottom: 10px;
  line-height: 1.6;
}

.calibration-result {
  margin-top: 10px;
  padding: 8px;
  background: rgba(0, 191, 255, 0.1);
  border-radius: 6px;
}

.calibration-result p {
  font-size: 11px;
  color: #00BFFF;
}

.calibration-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.calibration-buttons button {
  padding: 8px;
  background: #1a2040;
  border: 1px solid #2a3050;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.calibration-buttons button:hover:not(:disabled) {
  background: #252b50;
  border-color: #00BFFF;
}

.calibration-buttons button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.checkbox-item input[type="checkbox"] {
  accent-color: #00BFFF;
}

.checkbox-item label {
  font-size: 13px;
  color: #ccc;
  cursor: pointer;
}

.canvas-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.canvas-container canvas {
  background: #0a0e27;
  border-radius: 12px;
  border: 1px solid #2a3050;
  cursor: crosshair;
  width: 100%;
  max-width: 1000px;
}

.mouse-info {
  background: #1a1f3a;
  padding: 8px 15px;
  border-radius: 6px;
  font-size: 13px;
  color: #00BFFF;
  text-align: center;
}

.spectrum-info {
  background: linear-gradient(135deg, #1a1f3a 0%, #0d1229 100%);
  border-radius: 12px;
  padding: 15px;
  border: 1px solid #2a3050;
}

.spectrum-info h3 {
  color: #00BFFF;
  font-size: 14px;
  margin-bottom: 10px;
}

.spectrum-lines {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.spectrum-line-tag {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  color: white;
  font-weight: bold;
}

.blackbody-info {
  font-size: 12px;
  color: #aaa;
  line-height: 1.8;
}

.blackbody-info p {
  margin: 4px 0;
}

.info-panel {
  background: linear-gradient(135deg, #1a1f3a 0%, #0d1229 100%);
  border-radius: 12px;
  padding: 15px;
  border: 1px solid #2a3050;
}

.info-panel h3 {
  color: #00BFFF;
  font-size: 14px;
  margin-bottom: 10px;
}

.info-panel p {
  font-size: 18px;
  color: #FFD700;
  font-family: 'Times New Roman', serif;
  margin-bottom: 10px;
}

.equation-params {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #888;
}
</style>
