import React, { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/utils'

interface HalftoneWaveCanvasProps {
  className?: string
  height?: number
}

interface OrganicWaveLayer {
  baseColor: [number, number, number]
  crestColor: [number, number, number]
  amp: number
  phaseOffset: number
  baseThickness: number
  maxDotSize: number
  verticalShift: number
  baseAlpha: number
}

export const HalftoneWaveCanvas: React.FC<HalftoneWaveCanvasProps> = ({
  className,
  height = 210,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const animFrameIdRef = useRef<number | null>(null)
  const [isVisible, setIsVisible] = useState(true)

  // Pause rendering when scrolled out of view to save battery and GPU
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting)
      },
      { threshold: 0.05 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !isVisible) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let width = canvas.parentElement?.clientWidth || window.innerWidth
    let canvasHeight = height

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.parentElement.clientWidth || window.innerWidth
      canvasHeight = height
      canvas.width = width * dpr
      canvas.height = canvasHeight * dpr
      canvas.style.width = `${width}px`
      canvas.style.height = `${canvasHeight}px`
      ctx.resetTransform?.()
      ctx.scale(dpr, dpr)
    }

    handleResize()
    window.addEventListener('resize', handleResize)

    // Physics constants for realistic acoustic/fluid waves:
    // SHARED_SPEED: fluid, elegant horizontal flow
    // SHARED_FREQ: natural wavelength creating 3 to 4 prominent undulating crests
    const SHARED_SPEED = 0.65
    const SHARED_FREQ = 0.0068

    // 4 organic layers with dynamic lighting (baseColor in shadows, crestColor on illuminated peaks):
    const layers: OrganicWaveLayer[] = [
      {
        baseColor: [147, 197, 253], // Soft Sky Blue
        crestColor: [224, 242, 254], // Light Ice Crest
        amp: 44,
        phaseOffset: 0.7,
        baseThickness: 26,
        maxDotSize: 2.4,
        verticalShift: -18,
        baseAlpha: 0.5,
      },
      {
        baseColor: [56, 189, 248], // Luminous Azure
        crestColor: [186, 230, 253], // Highlight Azure
        amp: 50,
        phaseOffset: 0.35,
        baseThickness: 30,
        maxDotSize: 3.2,
        verticalShift: -6,
        baseAlpha: 0.7,
      },
      {
        baseColor: [76, 155, 224], // Brand Light Blue
        crestColor: [125, 211, 252], // Bright Crest
        amp: 48,
        phaseOffset: 0,
        baseThickness: 28,
        maxDotSize: 2.8,
        verticalShift: 8,
        baseAlpha: 0.65,
      },
      {
        baseColor: [0, 110, 185], // CortechX Brand Blue
        crestColor: [56, 189, 248], // Azure Glow
        amp: 42,
        phaseOffset: -0.4,
        baseThickness: 25,
        maxDotSize: 2.5,
        verticalShift: 20,
        baseAlpha: 0.45,
      },
    ]

    const startTime = performance.now()
    const gridStepX = 12
    const gridStepY = 12

    const render = (now: number) => {
      const elapsed = (now - startTime) / 1000

      ctx.clearRect(0, 0, width, canvasHeight)

      const centerY = canvasHeight / 2
      const cols = Math.ceil(width / gridStepX) + 1
      const rows = Math.ceil(canvasHeight / gridStepY) + 1

      const t = elapsed * SHARED_SPEED

      // Calculate realistic Trochoidal / Stokes waveforms for each layer
      // Real fluid/acoustic waves have slightly sharpened crests and wider, smooth troughs
      const waveYs: Float32Array[] = []
      const waveThicknesses: Float32Array[] = []
      const waveNormals: Float32Array[] = []

      layers.forEach((layer) => {
        const yArr = new Float32Array(cols)
        const thickArr = new Float32Array(cols)
        const normArr = new Float32Array(cols)

        for (let col = 0; col < cols; col++) {
          const x = col * gridStepX

          // Natural acoustic envelope: waves swell and breathe across the landscape
          const envelope =
            0.82 + 0.24 * Math.sin(x * 0.0014 - t * 0.3) * Math.cos(x * 0.0007 + t * 0.15)

          const effectiveAmp = layer.amp * envelope

          // Trochoidal/Stokes formulation:
          // theta1 = fundamental wave traveling horizontally
          // theta2 = second harmonic sharpening the crests
          const theta1 = x * SHARED_FREQ - t + layer.phaseOffset
          const theta2 = theta1 * 2 + 0.3

          // Asymmetrical wave profile: peaked peaks, rounded troughs (realistic wave physics)
          const stokesWave =
            Math.sin(theta1) +
            0.26 * Math.sin(theta1) * Math.cos(theta1) +
            0.18 * Math.sin(theta2)

          const yWave = stokesWave * effectiveAmp
          yArr[col] = centerY + layer.verticalShift + yWave

          // Acoustic compression: the ribbon naturally thickens at crests and thins at troughs
          const crestFactor = Math.max(0, -yWave / effectiveAmp) // 1 at peak, 0 at trough
          thickArr[col] = layer.baseThickness * (0.85 + crestFactor * 0.35)
          normArr[col] = crestFactor
        }

        waveYs.push(yArr)
        waveThicknesses.push(thickArr)
        waveNormals.push(normArr)
      })

      // Render all layers with volumetric lighting and refined square halftone dots
      layers.forEach((layer, lIdx) => {
        const lineYs = waveYs[lIdx]
        const thicknesses = waveThicknesses[lIdx]
        const crestFactors = waveNormals[lIdx]
        const maxDot = layer.maxDotSize
        const [baseR, baseG, baseB] = layer.baseColor
        const [crestR, crestG, crestB] = layer.crestColor

        for (let col = 0; col < cols; col++) {
          const x = col * gridStepX
          const waveY = lineYs[col]
          const thickness = thicknesses[col]
          const crestFactor = crestFactors[col]

          // Dynamic light interpolation: crests catch bright light, troughs sit in deeper color
          const r = Math.round(baseR + (crestR - baseR) * crestFactor * 0.7)
          const g = Math.round(baseG + (crestG - baseG) * crestFactor * 0.7)
          const b = Math.round(baseB + (crestB - baseB) * crestFactor * 0.7)

          const startRow = Math.max(0, Math.floor((waveY - thickness * 1.35) / gridStepY))
          const endRow = Math.min(rows, Math.ceil((waveY + thickness * 1.35) / gridStepY))

          for (let row = startRow; row <= endRow; row++) {
            const y = row * gridStepY
            const dist = Math.abs(y - waveY)

            if (dist < thickness) {
              const normDist = dist / thickness
              // Smooth exponential decay from wave centerline
              const intensity = Math.pow(1 - normDist, 1.6)

              if (intensity > 0.07) {
                // Crests have slightly denser/larger dots, troughs have finer dots
                const sizeBonus = 1 + crestFactor * 0.25
                const dotSize = Math.max(
                  0.8,
                  Math.min(maxDot * sizeBonus, intensity * maxDot * sizeBonus)
                )

                const alpha = Math.min(
                  0.88,
                  Math.max(0.08, intensity * layer.baseAlpha * (0.9 + crestFactor * 0.2))
                )

                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
                // Draw refined square pixel dot
                ctx.fillRect(
                  Math.round(x - dotSize / 2),
                  Math.round(y - dotSize / 2),
                  Math.round(dotSize),
                  Math.round(dotSize)
                )
              }
            }
          }
        }
      })

      animFrameIdRef.current = requestAnimationFrame(render)
    }

    animFrameIdRef.current = requestAnimationFrame(render)

    return () => {
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current)
      }
      window.removeEventListener('resize', handleResize)
    }
  }, [height, isVisible])

  return (
    <div
      ref={containerRef}
      className={cn('w-full overflow-hidden select-none', className)}
      style={{ height }}
    >
      <canvas ref={canvasRef} className="w-full h-full block" />
    </div>
  )
}
