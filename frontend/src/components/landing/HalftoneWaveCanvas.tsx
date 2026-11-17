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
  baseThickness: number
  maxDotSize: number
  verticalShift: number
  baseAlpha: number
  phaseOffset?: number
  envelopeOffset?: number
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
    const pointer = { x: 0, y: 0, strength: 0, active: false }
    const disturbance = { x: 0, y: 0, strength: 0 }
    const interactionRadius = 120
    const maxDisplacement = 20

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerType === 'touch' && event.buttons === 0) return
      const rect = canvas.getBoundingClientRect()
      pointer.x = event.clientX - rect.left
      pointer.y = event.clientY - rect.top
      pointer.active = true
    }
    const handlePointerLeave = () => {
      pointer.active = false
    }
    const handlePointerDown = (event: PointerEvent) => {
      handlePointerMove(event)
      const rect = canvas.getBoundingClientRect()
      disturbance.x = event.clientX - rect.left
      disturbance.y = event.clientY - rect.top
      disturbance.strength = 1
    }

    canvas.addEventListener('pointermove', handlePointerMove)
    canvas.addEventListener('pointerdown', handlePointerDown)
    canvas.addEventListener('pointerleave', handlePointerLeave)
    canvas.addEventListener('pointerup', handlePointerLeave)
    canvas.addEventListener('pointercancel', handlePointerLeave)

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

    // Shared phase keeps all layers narrow where the wave crosses its center axis.
    const SHARED_SPEED = 0.65
    const SHARED_FREQ = 0.011

    // Blue layers and a translucent black wave offset by 70 degrees.
    const layers: OrganicWaveLayer[] = [
      {
        baseColor: [147, 197, 253], // Soft Sky Blue
        crestColor: [224, 242, 254], // Light Ice Crest
        amp: 100,
        baseThickness: 34,
        maxDotSize: 3,
        verticalShift: -18,
        baseAlpha: 0.4,
      },
      {
        baseColor: [56, 189, 248], // Luminous Azure
        crestColor: [186, 230, 253], // Highlight Azure
        amp: 110,
        baseThickness: 38,
        maxDotSize: 3.8,
        verticalShift: -6,
        baseAlpha: 0.5,
      },
      {
        baseColor: [76, 155, 224], // Brand Light Blue
        crestColor: [125, 211, 252], // Bright Crest
        amp: 107,
        baseThickness: 36,
        maxDotSize: 3.5,
        verticalShift: 8,
        baseAlpha: 0.5,
      },
      {
        baseColor: [0, 110, 185], // CortechX Brand Blue
        crestColor: [56, 189, 248], // Azure Glow
        amp: 98,
        baseThickness: 33,
        maxDotSize: 3.1,
        verticalShift: 20,
        baseAlpha: 0.4,
      },
      {
        baseColor: [0, 0, 0],
        crestColor: [0, 0, 0],
        amp: 105,
        baseThickness: 36,
        maxDotSize: 3.5,
        verticalShift: 0,
        baseAlpha: 0.16,
        phaseOffset: (70 * Math.PI) / 180,
        envelopeOffset: 1.4,
      },
    ]

    const startTime = performance.now()
    const gridStepX = 8
    const gridStepY = 8
    let previousFrame = startTime

    const render = (now: number) => {
      const elapsed = (now - startTime) / 1000
      const delta = Math.min((now - previousFrame) / 1000, 0.1)
      previousFrame = now
      const targetStrength = pointer.active ? 1 : 0
      pointer.strength += (targetStrength - pointer.strength) * (1 - Math.exp(-delta * 7))
      disturbance.strength *= Math.exp(-delta * 2.5)

      ctx.clearRect(0, 0, width, canvasHeight)

      const centerY = canvasHeight / 2
      const cols = Math.ceil(width / gridStepX) + 1
      const rows = Math.ceil(canvasHeight / gridStepY) + 1

      const t = elapsed * SHARED_SPEED

      // The layers share a sine wave and taper towards the center axis.
      const waveYs: Float32Array[] = []
      const waveThicknesses: Float32Array[] = []
      const waveNormals: Float32Array[] = []

      layers.forEach((layer) => {
        const yArr = new Float32Array(cols)
        const thickArr = new Float32Array(cols)
        const normArr = new Float32Array(cols)

        for (let col = 0; col < cols; col++) {
          const x = col * gridStepX

          // Slow, overlapping envelopes give the wave the changing energy of speech.
          const envelopePhase = layer.envelopeOffset ?? 0
          const envelope =
            0.72 +
            0.2 * Math.sin(x * 0.003 - t * 0.7 + envelopePhase) +
            0.12 * Math.sin(x * 0.007 + t * 1.1 + envelopePhase)
          const phase = x * SHARED_FREQ - t + 0.18 * Math.sin(x * 0.002 - t * 0.4)
          const sine = Math.sin(phase + (layer.phaseOffset ?? 0))
          const yWave = sine * (layer.amp + layer.verticalShift * 0.3) * envelope
          // Fill the space between the sine curve and the center axis.
          yArr[col] = centerY + yWave * 0.55

          const crestFactor = Math.abs(sine)
          thickArr[col] = 2 + (Math.abs(yWave) * 0.45 + layer.baseThickness * 0.3) * crestFactor
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
              // Keep the fill soft while emphasizing the outer sine-wave edge.
              const outerSide = Math.sign(waveY - centerY) * (y - waveY)
              const edge = Math.max(0, outerSide / thickness)
              const intensity = Math.min(
                1,
                Math.pow(1 - normDist, 1.6) * 0.55 + Math.pow(edge, 1.5) * 1.4
              )

              if (intensity > 0.07) {
                // Crests have slightly denser/larger dots, troughs have finer dots
                const sizeBonus = 1 + crestFactor * 0.25
                const dotSize = Math.max(
                  0.8,
                  Math.min(maxDot * sizeBonus, intensity * maxDot * sizeBonus)
                )

                const hoverDistance = Math.hypot(x - pointer.x, y - pointer.y)
                const glow = Math.max(0, 1 - hoverDistance / interactionRadius) * pointer.strength
                const alpha = Math.min(
                  1,
                  Math.max(0.02, intensity * layer.baseAlpha * (0.9 + crestFactor * 0.2)) +
                    glow * intensity * (layer.phaseOffset ? layer.baseAlpha : 1)
                )

                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
                const dx = x - disturbance.x
                const dy = y - disturbance.y
                const distance = Math.hypot(dx, dy)
                const influence = Math.max(0, 1 - distance / interactionRadius)
                const displacement = maxDisplacement * influence * influence * disturbance.strength
                const directionX = distance > 0 ? dx / distance : 0
                const directionY = distance > 0 ? dy / distance : -1
                // Draw refined square pixel dot
                ctx.fillRect(
                  Math.round(x + directionX * displacement - dotSize / 2),
                  Math.round(y + directionY * displacement - dotSize / 2),
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
      canvas.removeEventListener('pointermove', handlePointerMove)
      canvas.removeEventListener('pointerdown', handlePointerDown)
      canvas.removeEventListener('pointerleave', handlePointerLeave)
      canvas.removeEventListener('pointerup', handlePointerLeave)
      canvas.removeEventListener('pointercancel', handlePointerLeave)
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
