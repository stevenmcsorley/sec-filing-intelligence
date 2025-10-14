"use client"

import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { HistoricalPrice } from '@/services/api/price.service'

interface FilingCorrelation {
  date: string
  formType: string
  title: string
  priceChangePercent: number
  volumeSpike: boolean
  correlationStrength: 'strong' | 'moderate' | 'weak'
}

interface FilingCorrelationChartProps {
  historicalPrices: HistoricalPrice[]
  filingCorrelations: FilingCorrelation[]
  height?: number
  className?: string
}

export const FilingCorrelationChart: React.FC<FilingCorrelationChartProps> = ({
  historicalPrices,
  filingCorrelations,
  height = 300,
  className = ''
}) => {
  const chartOption = useMemo(() => {
    if (!historicalPrices.length || !filingCorrelations.length) {
      return {
        title: {
          text: 'No Correlation Data Available',
          left: 'center',
          top: 'middle',
          textStyle: {
            color: '#9ca3af',
            fontSize: 16
          }
        }
      }
    }

    // Prepare price data
    const priceData = historicalPrices.map(price => ({
      date: price.date,
      close: price.close,
      volume: price.volume
    }))

    // Prepare filing correlation data
    const correlationData = filingCorrelations.map(filing => ({
      date: filing.date,
      priceChange: filing.priceChangePercent,
      formType: filing.formType,
      title: filing.title,
      volumeSpike: filing.volumeSpike,
      strength: filing.correlationStrength
    }))

    // Combine data for scatter plot
    const scatterData = correlationData.map(filing => {
      const pricePoint = priceData.find(p => p.date === filing.date)
      return [
        filing.date,
        filing.priceChange,
        filing.formType,
        filing.title,
        filing.volumeSpike,
        filing.strength
      ]
    })

    return {
      backgroundColor: 'transparent',
      title: {
        text: 'Filing Impact on Price Movement',
        left: 'center',
        textStyle: {
          color: '#f9fafb',
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        borderColor: '#374151',
        borderWidth: 1,
        textStyle: {
          color: '#f9fafb'
        },
        formatter: function (params: any) {
          const data = params.data
          const [date, priceChange, formType, title, volumeSpike, strength] = data
          
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">${formType} - ${date}</div>
              <div>Price Change: <span style="color: ${priceChange >= 0 ? '#10b981' : '#ef4444'}">${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%</span></div>
              <div>Volume Spike: ${volumeSpike ? 'Yes' : 'No'}</div>
              <div>Correlation: <span style="color: ${strength === 'strong' ? '#ef4444' : strength === 'moderate' ? '#f59e0b' : '#10b981'}">${strength}</span></div>
              <div style="margin-top: 4px; font-size: 12px;">${title}</div>
            </div>
          `
        }
      },
      legend: {
        data: ['Price Change %'],
        textStyle: {
          color: '#f9fafb'
        },
        top: 40
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '20%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: historicalPrices.map(p => p.date),
        axisLabel: {
          color: '#9ca3af',
          formatter: function (value: string) {
            return new Date(value).toLocaleDateString('en-US', { 
              month: 'short', 
              day: 'numeric' 
            })
          }
        },
        splitLine: {
          lineStyle: {
            color: '#374151'
          }
        }
      },
      yAxis: {
        type: 'value',
        name: 'Price Change %',
        nameTextStyle: {
          color: '#f9fafb'
        },
        axisLabel: {
          color: '#9ca3af',
          formatter: function (value: number) {
            return value >= 0 ? `+${value.toFixed(1)}%` : `${value.toFixed(1)}%`
          }
        },
        splitLine: {
          lineStyle: {
            color: '#374151'
          }
        },
        axisLine: {
          lineStyle: {
            color: '#374151'
          }
        }
      },
      series: [
        {
          name: 'Price Change %',
          type: 'scatter',
          data: scatterData,
          symbolSize: function (data: any) {
            const [, , , , volumeSpike, strength] = data
            let size = 8
            if (volumeSpike) size += 4
            if (strength === 'strong') size += 4
            return size
          },
          itemStyle: {
            color: function (params: any) {
              const [, priceChange, , , , strength] = params.data
              if (strength === 'strong') return '#ef4444'
              if (strength === 'moderate') return '#f59e0b'
              return '#10b981'
            },
            borderColor: function (params: any) {
              const [, , , , volumeSpike] = params.data
              return volumeSpike ? '#ffffff' : 'transparent'
            },
            borderWidth: 2
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    }
  }, [historicalPrices, filingCorrelations])

  return (
    <div className={`w-full ${className}`}>
      <ReactECharts
        option={chartOption}
        style={{ height: `${height}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  )
}

export default FilingCorrelationChart
