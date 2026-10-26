import { useEffect, useRef } from 'react'

const vertexSource = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`

const fragmentSource = `
precision highp float;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_audio;
uniform float u_state;

float sphere(vec3 p) {
  float pulse = sin(p.y * 8.0 + u_time * 1.6) * sin(p.x * 7.0 - u_time) * 0.012;
  float voice = u_audio * 0.045 * sin(p.x * 16.0 + p.y * 10.0 + u_time * 3.0);
  return length(p) - (0.77 + pulse + voice);
}
vec3 normalAt(vec3 p) {
  vec2 e = vec2(0.002, 0.0);
  return normalize(vec3(sphere(p + e.xyy) - sphere(p - e.xyy), sphere(p + e.yxy) - sphere(p - e.yxy), sphere(p + e.yyx) - sphere(p - e.yyx)));
}
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution) / min(u_resolution.x, u_resolution.y);
  vec3 ro = vec3(0.0, 0.0, 2.8);
  vec3 rd = normalize(vec3(uv, -1.85));
  float t = 0.0;
  bool hit = false;
  for (int i = 0; i < 72; i++) {
    float d = sphere(ro + rd * t);
    if (d < 0.0015) { hit = true; break; }
    t += d * 0.72;
    if (t > 5.0) break;
  }
  float radius = length(uv);
  float glow = exp(-abs(radius - 0.39) * 34.0) * (0.06 + u_audio * 0.22);
  vec3 color = vec3(0.78, 0.46, 0.23) * glow + vec3(0.91, 0.89, 0.82) * glow * 0.65;
  float alpha = glow * 0.3;
  if (hit) {
    vec3 p = ro + rd * t;
    vec3 n = normalAt(p);
    vec3 view = -rd;
    vec3 lightA = normalize(vec3(-0.72, 0.65, 1.2));
    vec3 lightB = normalize(vec3(0.8, -0.35, 0.9));
    float fresnel = pow(1.0 - max(dot(n, view), 0.0), 2.2);
    float specA = pow(max(dot(reflect(-lightA, n), view), 0.0), 52.0);
    float specB = pow(max(dot(reflect(-lightB, n), view), 0.0), 34.0);
    float diffuse = max(dot(n, lightA), 0.0);
    float rimCyan = pow(max(dot(n, normalize(vec3(-0.8, 0.1, 0.7))), 0.0), 2.0);
    float rimViolet = pow(max(dot(n, normalize(vec3(0.8, -0.25, 0.55))), 0.0), 2.0);
    vec3 deep = vec3(0.04, 0.11, 0.07);
    vec3 glass = deep * (0.68 + diffuse * 0.24);
    glass += vec3(0.91, 0.89, 0.82) * (rimCyan * 0.85 + specA * 0.92);
    glass += vec3(0.85, 0.46, 0.20) * (rimViolet * 0.75 + specB * 0.45);
    glass += vec3(0.30, 0.50, 0.36) * fresnel * (0.42 + u_audio * 0.45 + (u_state > 1.5 ? 0.18 : 0.0));
    float highlight = pow(max(dot(n, normalize(vec3(-0.4, 0.82, 1.0))), 0.0), 18.0);
    glass += vec3(0.97, 0.96, 0.94) * highlight * 0.20;
    color = glass;
    alpha = 0.84 + fresnel * 0.15;
  }
  gl_FragColor = vec4(color, alpha);
}
`

function compile(gl, type, source) {
  const shader = gl.createShader(type)
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader)
    return null
  }
  return shader
}

export default function VoiceVisualizer({ state = 'idle', analyser, theme = 'dark' }) {
  const canvasRef = useRef(null)
  const waveformRef = useRef(null)
  const fallbackRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const fallback = fallbackRef.current
    const gl = canvas?.getContext('webgl', { alpha: true, antialias: true, powerPreference: 'low-power' })
    const showFallback = () => {
      if (canvas) canvas.hidden = true
      if (fallback) fallback.hidden = false
    }
    if (!gl) { showFallback(); return undefined }
    const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource)
    const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource)
    if (!vertex || !fragment) { showFallback(); return undefined }
    const program = gl.createProgram()
    gl.attachShader(program, vertex)
    gl.attachShader(program, fragment)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { showFallback(); return undefined }
    canvas.hidden = false
    if (fallback) fallback.hidden = true
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW)
    gl.useProgram(program)
    const position = gl.getAttribLocation(program, 'position')
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
    const resolution = gl.getUniformLocation(program, 'u_resolution')
    const time = gl.getUniformLocation(program, 'u_time')
    const audio = gl.getUniformLocation(program, 'u_audio')
    const mode = gl.getUniformLocation(program, 'u_state')
    const samples = analyser ? new Uint8Array(analyser.fftSize) : null
    let frame = 0
    let started = performance.now()
    let lastPaint = 0
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let visible = typeof IntersectionObserver === 'undefined'
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      const width = Math.max(1, Math.floor(canvas.clientWidth * dpr))
      const height = Math.max(1, Math.floor(canvas.clientHeight * dpr))
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width
        canvas.height = height
        gl.viewport(0, 0, width, height)
      }
    }
    const drawWave = (level, now) => {
      const wave = waveformRef.current
      const context = wave?.getContext('2d')
      if (!context) return
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      const width = Math.max(1, Math.floor(wave.clientWidth * dpr))
      const height = Math.max(1, Math.floor(wave.clientHeight * dpr))
      if (wave.width !== width || wave.height !== height) { wave.width = width; wave.height = height }
      context.clearRect(0, 0, width, height)
      const center = height * 0.5
      const listening = state === 'listening' && analyser && samples
      const speaking = state === 'speaking'
      const amp = listening ? Math.max(3, level * height * 0.39) : speaking ? height * 0.22 : state === 'processing' ? height * 0.10 : height * 0.035
      const cycle = now * (speaking ? 0.007 : 0.003)
      const points = 180
      const path = (spread) => {
        context.beginPath()
        for (let i = 0; i <= points; i += 1) {
          const x = (i / points) * width
          const nx = i / points
          let signal
          if (listening) {
            const index = Math.floor(nx * (samples.length - 1))
            signal = ((samples[index] - 128) / 128) * height * 0.55
          } else {
            const envelope = 0.25 + 0.75 * Math.pow(Math.sin(nx * Math.PI), 0.8)
            signal = (Math.sin(nx * 30 + cycle) * 0.48 + Math.sin(nx * 62 - cycle * 1.7) * 0.27 + Math.sin(nx * 95 + cycle * 0.6) * 0.12) * amp * envelope
          }
          const y = center + signal * spread
          if (i === 0) context.moveTo(x, y); else context.lineTo(x, y)
        }
        context.stroke()
      }
      context.save()
      context.lineCap = 'round'
      context.lineJoin = 'round'
      context.shadowBlur = 17 * dpr
      context.shadowColor = '#C8763A'
      const gradient = context.createLinearGradient(0, 0, width, 0)
      gradient.addColorStop(0, 'rgba(200, 118, 58, .20)')
      gradient.addColorStop(.28, '#D98B50')
      gradient.addColorStop(.51, '#F7F5EF')
      gradient.addColorStop(.74, '#E9E2D0')
      gradient.addColorStop(1, 'rgba(200, 118, 58, .28)')
      context.strokeStyle = gradient
      context.lineWidth = 2.2 * dpr
      path(1)
      context.shadowBlur = 0
      context.strokeStyle = 'rgba(247, 245, 239, .72)'
      context.lineWidth = 0.65 * dpr
      path(0.55)
      context.restore()
    }
    const draw = (now) => {
      if (!visible) return
      if (!reducedMotion) frame = requestAnimationFrame(draw)
      if (now - lastPaint < 32) return
      lastPaint = now
      resize()
      let level = 0
      if (analyser && samples) {
        analyser.getByteTimeDomainData(samples)
        let energy = 0
        for (let i = 0; i < samples.length; i += 4) {
          const value = (samples[i] - 128) / 128
          energy += value * value
        }
        level = Math.min(1, Math.sqrt(energy / (samples.length / 4)) * 4.2)
      }
      const stateMode = state === 'listening' ? 1 : state === 'processing' ? 2 : state === 'speaking' ? 3 : state === 'error' ? 4 : 0
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.enable(gl.BLEND)
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)
      gl.uniform2f(resolution, canvas.width, canvas.height)
      gl.uniform1f(time, (now - started) / 1000)
      gl.uniform1f(audio, state === 'listening' ? level : state === 'speaking' ? 0.48 : state === 'processing' ? 0.24 : 0.03)
      gl.uniform1f(mode, stateMode)
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      drawWave(level, now)
    }
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => {
      resize()
      if (reducedMotion && visible) { cancelAnimationFrame(frame); frame = requestAnimationFrame(draw) }
    })
    observer?.observe(canvas)
    const visibilityObserver = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      if (visible && frame === 0) frame = requestAnimationFrame(draw)
      if (!visible) { cancelAnimationFrame(frame); frame = 0 }
    }, { rootMargin: '100px' })
    visibilityObserver?.observe(canvas)
    if (visible) frame = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(frame)
      observer?.disconnect()
      visibilityObserver?.disconnect()
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
      gl.deleteShader(vertex)
      gl.deleteShader(fragment)
      gl.getExtension('WEBGL_lose_context')?.loseContext()
    }
  }, [analyser, state, theme])

  return (
    <div className={`voice-visualizer visualizer-${state}`} role="img" aria-label={`REDELIVER voice agent, ${state}`}>
      <div className="orb-ring orb-ring-a" aria-hidden="true" />
      <div className="orb-ring orb-ring-b" aria-hidden="true" />
      <canvas ref={canvasRef} className="orb-glass" aria-hidden="true" />
      <canvas ref={waveformRef} className="orb-waveform" aria-hidden="true" />
      <div className="orb-platform" aria-hidden="true" />
      <div ref={fallbackRef} className="orb-fallback" hidden aria-hidden="true" />
      <span className="orb-label">{state === 'listening' ? 'Listening' : state === 'processing' ? 'Thinking' : state === 'speaking' ? 'Speaking' : state === 'error' ? 'Reconnect' : 'Ready'}</span>
    </div>
  )
}
