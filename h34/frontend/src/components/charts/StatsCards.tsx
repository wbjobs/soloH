import { TrendingUp, TrendingDown, Grid3X3, AlertTriangle, Minus } from 'lucide-react'
import { RISK_THRESHOLDS } from '@/types/map'
import type { RiskGrid } from '@/types'

interface StatsCardsProps {
  data: RiskGrid[]
  yesterdayData?: RiskGrid[]
}

interface CardData {
  title: string
  value: number
  change: number
  gradient: string
  icon: React.ReactNode
}

const countByRiskLevel = (data: RiskGrid[], min: number, max: number): number => {
  return data.filter((item) => item.risk_index >= min && item.risk_index < max).length
}

const calculateChange = (current: number, previous: number): number => {
  if (previous === 0) return current > 0 ? 100 : 0
  return Math.round(((current - previous) / previous) * 100)
}

export const StatsCards = ({ data, yesterdayData = [] }: StatsCardsProps) => {
  const totalGrids = data.length
  const yesterdayTotal = yesterdayData.length

  const highRiskCount = countByRiskLevel(data, RISK_THRESHOLDS.high, RISK_THRESHOLDS.extreme)
  const mediumRiskCount = countByRiskLevel(data, RISK_THRESHOLDS.medium, RISK_THRESHOLDS.high)
  const lowRiskCount = countByRiskLevel(data, 0, RISK_THRESHOLDS.medium)

  const yesterdayHigh = countByRiskLevel(yesterdayData, RISK_THRESHOLDS.high, RISK_THRESHOLDS.extreme)
  const yesterdayMedium = countByRiskLevel(yesterdayData, RISK_THRESHOLDS.medium, RISK_THRESHOLDS.high)
  const yesterdayLow = countByRiskLevel(yesterdayData, 0, RISK_THRESHOLDS.medium)

  const cards: CardData[] = [
    {
      title: '总网格数',
      value: totalGrids,
      change: calculateChange(totalGrids, yesterdayTotal),
      gradient: 'from-blue-500 to-blue-600',
      icon: <Grid3X3 className="w-8 h-8 text-white/90" />,
    },
    {
      title: '高风险',
      value: highRiskCount,
      change: calculateChange(highRiskCount, yesterdayHigh),
      gradient: 'from-red-500 to-red-600',
      icon: <AlertTriangle className="w-8 h-8 text-white/90" />,
    },
    {
      title: '中风险',
      value: mediumRiskCount,
      change: calculateChange(mediumRiskCount, yesterdayMedium),
      gradient: 'from-orange-500 to-orange-600',
      icon: <Minus className="w-8 h-8 text-white/90" />,
    },
    {
      title: '低风险',
      value: lowRiskCount,
      change: calculateChange(lowRiskCount, yesterdayLow),
      gradient: 'from-green-500 to-green-600',
      icon: <Minus className="w-8 h-8 text-white/90" />,
    },
  ]

  const renderChangeIcon = (change: number) => {
    if (change > 0) {
      return <TrendingUp className="w-4 h-4 text-white" />
    } else if (change < 0) {
      return <TrendingDown className="w-4 h-4 text-white" />
    }
    return <Minus className="w-4 h-4 text-white/70" />
  }

  const getChangeColor = (change: number) => {
    if (change > 0) return 'text-red-100'
    if (change < 0) return 'text-green-100'
    return 'text-white/70'
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`relative overflow-hidden rounded-xl bg-gradient-to-br ${card.gradient} p-5 shadow-lg`}
        >
          <div className="absolute top-0 right-0 -mt-2 -mr-2 w-24 h-24 bg-white/10 rounded-full blur-2xl" />
          <div className="absolute bottom-0 left-0 -mb-2 -ml-2 w-20 h-20 bg-black/10 rounded-full blur-2xl" />

          <div className="relative z-10">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-white/80 text-sm font-medium">{card.title}</p>
                <p className="text-3xl font-bold text-white mt-1">{card.value.toLocaleString()}</p>
              </div>
              <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
                {card.icon}
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {renderChangeIcon(card.change)}
              <span className={`text-sm font-medium ${getChangeColor(card.change)}`}>
                {Math.abs(card.change)}%
              </span>
              <span className="text-white/60 text-sm">较昨日</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default StatsCards
