/**
 * Zumo Audio Recorder Manager
 * Gerencia a captura simultânea de áudio do microfone do usuário e do áudio do sistema/abas do navegador.
 * Mixa as fontes via Web Audio API e grava em WebM/Opus para envio direto ao backend.
 */
class ZumoAudioRecorder {
  constructor() {
    this.audioContext = null;
    this.micStream = null;
    this.systemStream = null;
    this.destinationNode = null;
    this.mediaRecorder = null;
    this.recordedChunks = [];
    
    // Analisadores de áudio para VU Meters
    this.micAnalyser = null;
    this.systemAnalyser = null;
    this.micDataArray = null;
    this.systemDataArray = null;

    this.isRecording = false;
    this.isPaused = false;
    this.startTime = null;
    this.elapsedTime = 0;
    this.timerInterval = null;
    this.captureMode = 'both'; // 'both' ou 'mic_only'

    this.onTick = null; // callback para atualizar o cronômetro
    this.onStateChange = null; // callback para mudanças de estado
    this.onSourceEnded = null; // callback para encerramento inesperado de fonte de áudio
  }

  static isSupported() {
    return !!(
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      navigator.mediaDevices.getDisplayMedia &&
      (window.AudioContext || window.webkitAudioContext) &&
      window.MediaRecorder
    );
  }

  /**
   * Inicia a gravação de áudio combinada.
   * @param {Object} options
   * @param {string} options.mode - 'both' (microfone + abas/sistema) ou 'mic_only'
   * @param {Function} options.onTick - callback chamado a cada segundo com tempo decorrido em ms
   * @param {Function} options.onStateChange - callback de mudança de estado ('recording', 'paused', 'stopped')
   */
  async start({ mode = 'both', onTick = null, onStateChange = null, onSourceEnded = null } = {}) {
    if (this.isRecording) {
      throw new Error('A gravação já está em andamento.');
    }

    this.captureMode = mode;
    this.onTick = onTick;
    this.onStateChange = onStateChange;
    this.onSourceEnded = onSourceEnded;
    this.recordedChunks = [];

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this.audioContext = new AudioContextClass({ latencyHint: 'interactive' });
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    this.destinationNode = this.audioContext.createMediaStreamDestination();

    // 1. Capturar Microfone do Usuário
    try {
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
    } catch (err) {
      throw new Error(`Permissão de microfone negada ou indisponível: ${err.message}`);
    }

    const micSource = this.audioContext.createMediaStreamSource(this.micStream);
    this.micAnalyser = this.audioContext.createAnalyser();
    this.micAnalyser.fftSize = 256;
    this.micDataArray = new Uint8Array(this.micAnalyser.frequencyBinCount);

    const micGain = this.audioContext.createGain();
    micGain.gain.value = 1.0;

    micSource.connect(this.micAnalyser);
    this.micAnalyser.connect(micGain);
    micGain.connect(this.destinationNode);

    // 2. Capturar Áudio do Sistema / Abas (se modo 'both')
    if (this.captureMode === 'both') {
      try {
        this.systemStream = await navigator.mediaDevices.getDisplayMedia({
          video: {
            displaySurface: 'browser',
          },
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
        });
      } catch (err) {
        // Libera o microfone se o usuário cancelou o seletor de tela
        this.cleanupStreams();
        if (err.name === 'NotAllowedError') {
          throw new Error('Captura de tela/aba cancelada pelo usuário.');
        }
        throw new Error(`Falha ao capturar áudio da aba/sistema: ${err.message}`);
      }

      const systemAudioTracks = this.systemStream.getAudioTracks();
      if (!systemAudioTracks || systemAudioTracks.length === 0) {
        this.cleanupStreams();
        throw new Error(
          'Nenhum áudio foi detectado na seleção! Por favor, certifique-se de marcar a opção ' +
          '"Compartilhar áudio da aba" ou "Compartilhar áudio do sistema" ao selecionar a janela/aba.'
        );
      }

      // Trata interrupção caso o usuário clique em "Parar compartilhamento" no navegador
      const handleSystemTrackEnded = () => {
        if (this.isRecording) {
          console.warn('O compartilhamento de áudio da aba/sistema foi encerrado.');
          if (this.onSourceEnded) {
            this.onSourceEnded('system');
          }
        }
      };

      this.systemStream.getVideoTracks().forEach((track) => {
        track.onended = handleSystemTrackEnded;
      });

      systemAudioTracks.forEach((track) => {
        track.onended = handleSystemTrackEnded;
      });

      const systemAudioStream = new MediaStream(systemAudioTracks);
      const systemSource = this.audioContext.createMediaStreamSource(systemAudioStream);
      
      this.systemAnalyser = this.audioContext.createAnalyser();
      this.systemAnalyser.fftSize = 256;
      this.systemDataArray = new Uint8Array(this.systemAnalyser.frequencyBinCount);

      const systemGain = this.audioContext.createGain();
      systemGain.gain.value = 1.0;

      systemSource.connect(this.systemAnalyser);
      this.systemAnalyser.connect(systemGain);
      systemGain.connect(this.destinationNode);
    }

    // 3. Configurar MediaRecorder com o stream combinado
    const mimeTypesToTry = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];

    let selectedMimeType = '';
    for (const mime of mimeTypesToTry) {
      if (MediaRecorder.isTypeSupported(mime)) {
        selectedMimeType = mime;
        break;
      }
    }

    const recorderOptions = selectedMimeType ? { mimeType: selectedMimeType, audioBitsPerSecond: 128000 } : {};
    this.mediaRecorder = new MediaRecorder(this.destinationNode.stream, recorderOptions);

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.recordedChunks.push(event.data);
      }
    };

    this.mediaRecorder.start(1000); // Fatias de 1 segundo para maior resiliência
    this.isRecording = true;
    this.isPaused = false;
    this.startTime = Date.now();
    this.elapsedTime = 0;

    this.startTimer();

    if (this.onStateChange) {
      this.onStateChange('recording');
    }
  }

  startTimer() {
    this.stopTimer();
    this.timerInterval = setInterval(() => {
      if (this.isRecording && !this.isPaused) {
        this.elapsedTime = Date.now() - this.startTime;
        if (this.onTick) {
          this.onTick(this.elapsedTime);
        }
      }
    }, 500);
  }

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  pause() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.pause();
      this.isPaused = true;
      if (this.onStateChange) this.onStateChange('paused');
    }
  }

  resume() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
      this.mediaRecorder.resume();
      this.isPaused = false;
      this.startTime = Date.now() - this.elapsedTime;
      if (this.onStateChange) this.onStateChange('recording');
    }
  }

  /**
   * Finaliza a gravação e retorna o arquivo de áudio compactado.
   * @returns {Promise<{ blob: Blob, durationMs: number, mimeType: string }>}
   */
  async stop() {
    if (!this.isRecording) {
      throw new Error('Nenhuma gravação em andamento.');
    }

    this.stopTimer();

    return new Promise((resolve, reject) => {
      this.mediaRecorder.onerror = (err) => reject(err);

      this.mediaRecorder.onstop = () => {
        const mimeType = this.mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(this.recordedChunks, { type: mimeType });
        const finalDuration = this.elapsedTime;

        this.cleanup();
        if (this.onStateChange) this.onStateChange('stopped');

        resolve({
          blob,
          durationMs: finalDuration,
          mimeType,
        });
      };

      try {
        this.mediaRecorder.stop();
      } catch (err) {
        this.cleanup();
        reject(err);
      }
    });
  }

  /**
   * Retorna os níveis atuais de áudio (0.0 a 1.0) para atualização visual de VU meters.
   */
  getAudioLevels() {
    let micLevel = 0;
    let systemLevel = 0;

    if (this.micAnalyser && this.micDataArray) {
      this.micAnalyser.getByteFrequencyData(this.micDataArray);
      let sum = 0;
      for (let i = 0; i < this.micDataArray.length; i++) {
        sum += this.micDataArray[i];
      }
      micLevel = Math.min(1.0, (sum / this.micDataArray.length) / 128);
    }

    if (this.systemAnalyser && this.systemDataArray) {
      this.systemAnalyser.getByteFrequencyData(this.systemDataArray);
      let sum = 0;
      for (let i = 0; i < this.systemDataArray.length; i++) {
        sum += this.systemDataArray[i];
      }
      systemLevel = Math.min(1.0, (sum / this.systemDataArray.length) / 128);
    }

    return { micLevel, systemLevel };
  }

  cleanupStreams() {
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }
    if (this.systemStream) {
      this.systemStream.getTracks().forEach((track) => track.stop());
      this.systemStream = null;
    }
  }

  cleanup() {
    this.isRecording = false;
    this.isPaused = false;
    this.cleanupStreams();

    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        this.audioContext.close();
      } catch (e) {
        console.error('Erro ao fechar AudioContext:', e);
      }
      this.audioContext = null;
    }

    this.micAnalyser = null;
    this.systemAnalyser = null;
  }
}

// Expõe globalmente no navegador ou exporta como módulo
if (typeof window !== 'undefined') {
  window.ZumoAudioRecorder = ZumoAudioRecorder;
}
