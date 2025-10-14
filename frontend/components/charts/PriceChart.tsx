"use client"

import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { HistoricalPrice } from '@/services/api/price.service'

interface FilingMarker {
  date: string
  formType: string
  title: string
  impact: 'high' | 'medium' | 'low'
}

interface PriceChartProps {
  historicalPrices: HistoricalPrice[]
  filingMarkers?: FilingMarker[]
  height?: number
  showVolume?: boolean
  className?: string
}

export const PriceChart: React.FC<PriceChartProps> = ({
  historicalPrices,
  filingMarkers = [],
  height = 400,
  showVolume = true,
  className = ''
}) => {
  const chartOption = useMemo(() => {
    if (!historicalPrices.length) {
      return {
        title: {
          text: 'No Price Data Available',
          left: 'center',
          top: 'middle',
          textStyle: {
            color: '#9ca3af',
            fontSize: 16
          }
        }
      }
    }

    // Prepare candlestick data [open, close, low, high]
    const candlestickData = historicalPrices.map(price => [
      price.open,
      price.close,
      price.low,
      price.high
    ])

    // Prepare volume data
    const volumeData = historicalPrices.map(price => price.volume)

    // Prepare dates
    const dates = historicalPrices.map(price => price.date)

    // Prepare filing markers
    const filingAnnotations = filingMarkers.map(filing => ({
      name: filing.title,
      coord: [filing.date, historicalPrices.find(p => p.date === filing.date)?.high || 0],
      symbol: 'pin',
      symbolSize: 20,
      itemStyle: {
        color: filing.impact === 'high' ? '#ef4444' : filing.impact === 'medium' ? '#f59e0b' : '#10b981'
      },
      label: {
        show: true,
        position: 'top',
        formatter: filing.formType,
        fontSize: 10,
        color: '#fff',
        backgroundColor: filing.impact === 'high' ? '#ef4444' : filing.impact === 'medium' ? '#f59e0b' : '#10b981',
        borderRadius: 4,
        padding: [2, 6]
      }
    }))

    const baseOption = {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 1000,
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: {
            color: '#999'
          }
        },
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        borderColor: '#374151',
        borderWidth: 1,
        textStyle: {
          color: '#f9fafb'
        },
        formatter: function (params: any) {
          if (!params || params.length === 0) return ''
          
          const data = params[0]
          const date = data.axisValue
          const priceData = historicalPrices.find(p => p.date === date)
          
          if (!priceData) return ''
          
          const filing = filingMarkers.find(f => f.date === date)
          
          let tooltip = `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">${date}</div>
              <div>Open: $${priceData.open.toFixed(2)}</div>
              <div>High: $${priceData.high.toFixed(2)}</div>
              <div>Low: $${priceData.low.toFixed(2)}</div>
              <div>Close: $${priceData.close.toFixed(2)}</div>
              <div>Volume: ${priceData.volume.toLocaleString()}</div>
          `
          
          if (filing) {
            tooltip += `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #374151;">
                <div style="font-weight: bold; color: ${filing.impact === 'high' ? '#ef4444' : filing.impact === 'medium' ? '#f59e0b' : '#10b981'};">${filing.formType}</div>
                <div style="font-size: 12px;">${filing.title}</div>
              </div>
            `
          }
          
          tooltip += '</div>'
          return tooltip
        }
      },
      legend: {
        data: ['Price', 'Volume'],
        textStyle: {
          color: '#f9fafb'
        },
        top: 10
      },
      grid: [
        {
          left: '3%',
          right: '4%',
          top: '15%',
          height: showVolume ? '60%' : '80%'
        },
        {
          left: '3%',
          right: '4%',
          top: '80%',
          height: '15%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          min: 'dataMin',
          max: 'dataMax',
          axisLabel: {
            color: '#9ca3af',
            formatter: function (value: string) {
              return new Date(value).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
              })
            }
          }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { onZero: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          min: 'dataMin',
          max: 'dataMax'
        }
      ],
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true,
            areaStyle: {
              color: ['rgba(250,250,250,0.05)', 'rgba(200,200,200,0.05)']
            }
          },
          axisLabel: {
            color: '#9ca3af',
            formatter: function (value: number) {
              return '$' + value.toFixed(2)
            }
          },
          splitLine: {
            lineStyle: {
              color: '#374151'
            }
          }
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: Math.max(0, 100 - (historicalPrices.length * 0.3)),
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          top: '90%',
          start: Math.max(0, 100 - (historicalPrices.length * 0.3)),
          end: 100,
          backgroundColor: '#1f2937',
          borderColor: '#374151',
          fillerColor: 'rgba(59, 130, 246, 0.2)',
          selectedDataBackgroundColor: 'rgba(59, 130, 246, 0.3)',
          textStyle: {
            color: '#f9fafb'
          }
        }
      ],
      series: [
        {
          name: 'Price',
          type: 'candlestick',
          data: candlestickData,
          itemStyle: {
            color: '#10b981', // Green for up
            color0: '#ef4444', // Red for down
            borderColor: '#10b981',
            borderColor0: '#ef4444'
          },
          markPoint: {
            data: filingAnnotations,
            symbol: 'pin',
            symbolSize: 20,
            itemStyle: {
              color: '#ef4444'
            }
          }
        }
      ]
    }

    // Add volume series if requested
    if (showVolume) {
      (baseOption as any).series.push({
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
        itemStyle: {
          color: function (params: any) {
            const priceData = historicalPrices[params.dataIndex]
            return priceData.close >= priceData.open ? '#10b981' : '#ef4444'
          }
        }
      })
    }

    return baseOption
  }, [historicalPrices, filingMarkers, showVolume])

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

export default PriceChart
