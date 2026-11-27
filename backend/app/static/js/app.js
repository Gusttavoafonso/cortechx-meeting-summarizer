/**
 * CortechX Zumo - Application Controller
 * Coordena o fluxo de gravação, upload automático, polling de status e exibição de resumo.
 */

document.addEventListener('DOMContentLoaded', () => {
  const recorder = new ZumoAudioRecorder();
  let animationFrameId = null;
  let pollingInterval = null;
  let currentMeetingId = null;

  // Elementos do DOM
  const btnStartRecord = document.getElementById('btnStartRecord');
  const recordIdlePanel = document.getElementById('recordIdlePanel');
  const recordingActivePanel = document.getElementById('recordingActivePanel');
  const processingSection = document.getElementById('processingSection');
  const resultSection = document.getElementById('resultSection');

  const timerDisplay = document.getElementById('timerDisplay');
  const micVuBar = document.getElementById('micVuBar');
  const systemVuBar = document.getElementById('systemVuBar');
  const systemVuBox = document.getElementById('systemVuBox');

  const btnPause = document.getElementById('btnPause');
  const btnResume = document.getElementById('btnResume');
  const btnStop = document.getElementById('btnStop');
  const btnCancel = document.getElementById('btnCancel');
  const meetingTitleInput = document.getElementById('meetingTitleInput');

  const processingStatusText = document.getElementById('processingStatusText');
  const stepReceived = document.getElementById('stepReceived');
  const stepUploaded = document.getElementById('stepUploaded');
  const stepTranscribing = document.getElementById('stepTranscribing');
  const stepSummarizing = document.getElementById('stepSummarizing');
  const stepCompleted = document.getElementById('stepCompleted');

  const resultTitle = document.getElementById('resultTitle');
  const resultStatus = document.getElementById('resultStatus');
  const summaryObjective = document.getElementById('summaryObjective');
  const summaryContent = document.getElementById('summaryContent');
  const summaryKeyPoints = document.getElementById('summaryKeyPoints');
  const summaryDecisions = document.getElementById('summaryDecisions');
  const taskList = document.getElementById('taskList');
  const transcriptList = document.getElementById('transcriptList');
  const btnNewRecording = document.getElementById('btnNewRecording');
  const recentMeetingsContainer = document.getElementById('recentMeetingsContainer');
  const toastAlert = document.getElementById('toastAlert');

  // Elementos do Banner Interativo de Reunião
  const meetingPromptBanner = document.getElementById('meetingPromptBanner');
  const promptPlatform = document.getElementById('promptPlatform');
  const promptDetails = document.getElementById('promptDetails');
  const btnPromptRecord = document.getElementById('btnPromptRecord');
  const btnPromptDismiss = document.getElementById('btnPromptDismiss');
  let activePromptMeeting = null;

  if (btnPromptDismiss) {
    btnPromptDismiss.addEventListener('click', () => {
      if (meetingPromptBanner) meetingPromptBanner.style.display = 'none';
      activePromptMeeting = null;
    });
  }

  if (btnPromptRecord) {
    btnPromptRecord.addEventListener('click', () => {
      if (activePromptMeeting && meetingTitleInput) {
        meetingTitleInput.value = activePromptMeeting.title || '';
      }
      if (meetingPromptBanner) meetingPromptBanner.style.display = 'none';
      btnStartRecord.click();
    });
  }

  // Se executando dentro do Tauri, ouve eventos nativos de reunião detectada e ações da bandeja
  if (window.__TAURI__ && window.__TAURI__.event) {
    window.__TAURI__.event.listen('meeting-detected', (event) => {
      const meeting = event.payload;
      if (meeting && !recorder.isRecording) {
        activePromptMeeting = meeting;
        if (promptPlatform) promptPlatform.textContent = `Reunião detectada no ${meeting.platform || 'Aplicativo'}!`;
        if (promptDetails) promptDetails.textContent = `Chamada: "${meeting.title}". Deseja iniciar a gravação?`;
        if (meetingPromptBanner) meetingPromptBanner.style.display = 'flex';
      }
    });

    window.__TAURI__.event.listen('start-recording-action', () => {
      if (!recorder.isRecording && btnStartRecord) {
        btnStartRecord.click();
      }
    });
  }

  // Elementos de Autenticação
  const authModal = document.getElementById('authModal');
  const authForm = document.getElementById('authForm');
  const authNameField = document.getElementById('authNameField');
  const authName = document.getElementById('authName');
  const authEmail = document.getElementById('authEmail');
  const authPassword = document.getElementById('authPassword');
  const btnAuthSubmit = document.getElementById('btnAuthSubmit');
  const btnAuthToggle = document.getElementById('btnAuthToggle');
  const authToggleText = document.getElementById('authToggleText');
  const authModalTitle = document.getElementById('authModalTitle');
  const btnCloseAuth = document.getElementById('btnCloseAuth');
  const authNavContainer = document.getElementById('authNavContainer');
  const btnOpenLogin = document.getElementById('btnOpenLogin');

  let currentUser = null;
  let isRegisterMode = false;

  async function checkAuth() {
    try {
      const res = await fetch('/auth/me');
      if (res.ok) {
        currentUser = await res.json();
        renderAuthNav();
        fetchRecentMeetings();
      } else {
        currentUser = null;
        renderAuthNav();
      }
    } catch (e) {
      currentUser = null;
      renderAuthNav();
    }
  }

  function renderAuthNav() {
    if (!authNavContainer) return;
    if (currentUser) {
      authNavContainer.innerHTML = `
        <span style="font-size: 0.85rem; color: #cbd5e1;">👤 ${currentUser.name || currentUser.email}</span>
        <button id="btnLogout" class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">Sair</button>
      `;
      document.getElementById('btnLogout')?.addEventListener('click', async () => {
        await fetch('/auth/logout', { method: 'POST' });
        currentUser = null;
        renderAuthNav();
        showToast('Você saiu da sua conta.');
        if (recentMeetingsContainer) {
          recentMeetingsContainer.innerHTML = '<div style="color: var(--text-muted); grid-column: 1/-1;">Faça login para ver seu histórico.</div>';
        }
      });
    } else {
      authNavContainer.innerHTML = `
        <button id="btnOpenLogin" class="btn btn-secondary" style="padding: 0.35rem 0.85rem; font-size: 0.85rem;">Entrar</button>
      `;
      document.getElementById('btnOpenLogin')?.addEventListener('click', () => {
        openAuthModal(false);
      });
    }
  }

  function openAuthModal(register = false) {
    if (!authModal) return;
    isRegisterMode = register;
    authModalTitle.textContent = isRegisterMode ? 'Criar Conta no Zumo' : 'Entrar no Zumo';
    btnAuthSubmit.textContent = isRegisterMode ? 'Criar Conta' : 'Entrar';
    authNameField.style.display = isRegisterMode ? 'block' : 'none';
    authToggleText.textContent = isRegisterMode ? 'Já possui conta?' : 'Não tem uma conta?';
    btnAuthToggle.textContent = isRegisterMode ? 'Entrar' : 'Criar Conta';
    authModal.style.display = 'flex';
  }

  function closeAuthModal() {
    if (authModal) authModal.style.display = 'none';
  }

  btnOpenLogin?.addEventListener('click', () => openAuthModal(false));
  btnCloseAuth?.addEventListener('click', closeAuthModal);

  btnAuthToggle?.addEventListener('click', () => {
    openAuthModal(!isRegisterMode);
  });

  authForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = authEmail.value.trim();
    const password = authPassword.value;
    const name = authName.value.trim();

    try {
      btnAuthSubmit.disabled = true;
      btnAuthSubmit.textContent = 'Processando...';

      if (isRegisterMode) {
        const res = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, name: name || 'Usuário' }),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Erro ao criar conta.');
        }
      }

      // Login
      const loginRes = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!loginRes.ok) {
        const data = await loginRes.json();
        throw new Error(data.detail || 'E-mail ou senha incorretos.');
      }

      currentUser = await loginRes.json();
      renderAuthNav();
      closeAuthModal();
      showToast(`Bem-vindo, ${currentUser.name || 'ao Zumo'}!`);
      fetchRecentMeetings();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btnAuthSubmit.disabled = false;
      btnAuthSubmit.textContent = isRegisterMode ? 'Criar Conta' : 'Entrar';
    }
  });

  // Seletores de fonte
  const radioSourceBoth = document.getElementById('sourceBoth');
  const radioSourceMic = document.getElementById('sourceMic');

  // Formatação de tempo mm:ss
  function formatTime(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  // Notificações Toast
  function showToast(message, isError = false) {
    if (!toastAlert) return;
    toastAlert.textContent = message;
    toastAlert.style.borderColor = isError ? 'var(--danger-color)' : 'var(--accent-primary)';
    toastAlert.style.display = 'block';
    setTimeout(() => {
      toastAlert.style.display = 'none';
    }, 4500);
  }

  // Atualização dos VU Meters
  function updateVuMeters() {
    if (recorder.isRecording && !recorder.isPaused) {
      const { micLevel, systemLevel } = recorder.getAudioLevels();
      if (micVuBar) micVuBar.style.width = `${Math.min(100, Math.round(micLevel * 100))}%`;
      if (systemVuBar) systemVuBar.style.width = `${Math.min(100, Math.round(systemLevel * 100))}%`;
    }
    animationFrameId = requestAnimationFrame(updateVuMeters);
  }

  // Iniciar Gravação
  btnStartRecord.addEventListener('click', async () => {
    if (!currentUser) {
      showToast('Por favor, faça login ou entre com a conta de demonstração para gravar.', false);
      openAuthModal(false);
      return;
    }

    if (!ZumoAudioRecorder.isSupported()) {
      showToast('Seu navegador não suporta a gravação de áudio WebRTC / MediaRecorder.', true);
      return;
    }

    const mode = radioSourceBoth.checked ? 'both' : 'mic_only';
    if (mode === 'mic_only' && systemVuBox) {
      systemVuBox.style.display = 'none';
    } else if (systemVuBox) {
      systemVuBox.style.display = 'block';
    }

    try {
      await recorder.start({
        mode,
        onTick: (elapsedMs) => {
          if (timerDisplay) timerDisplay.textContent = formatTime(elapsedMs);
        },
        onStateChange: (state) => {
          if (state === 'paused') {
            btnPause.style.display = 'none';
            btnResume.style.display = 'inline-flex';
          } else if (state === 'recording') {
            btnPause.style.display = 'inline-flex';
            btnResume.style.display = 'none';
          }
        },
        onSourceEnded: (source) => {
          if (source === 'system') {
            recorder.pause();
            showToast('Aviso: O áudio da aba foi encerrado no navegador. A gravação foi pausada.', true);
          }
        },
      });

      // Alterna interface para gravação ativa
      recordIdlePanel.style.display = 'none';
      recordingActivePanel.style.display = 'flex';
      processingSection.style.display = 'none';
      resultSection.style.display = 'none';

      animationFrameId = requestAnimationFrame(updateVuMeters);
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // Pausar Gravação
  btnPause.addEventListener('click', () => {
    recorder.pause();
  });

  // Retomar Gravação
  btnResume.addEventListener('click', () => {
    recorder.resume();
  });

  // Cancelar Gravação
  btnCancel.addEventListener('click', async () => {
    if (confirm('Deseja descartar a gravação atual?')) {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      try {
        await recorder.stop();
      } catch (e) {
        recorder.cleanup();
      }
      resetToIdle();
      showToast('Gravação cancelada.');
    }
  });

  // Finalizar e Processar Reunião
  btnStop.addEventListener('click', async () => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);

    try {
      btnStop.disabled = true;
      btnStop.textContent = 'Finalizando gravação...';

      const { blob, mimeType } = await recorder.stop();
      
      // Transiciona interface para processamento
      recordingActivePanel.style.display = 'none';
      processingSection.style.display = 'block';
      processingStatusText.textContent = 'Enviando áudio para o servidor...';
      updatePipelineStep('uploaded');

      // Título da reunião (usa input ou data/hora atual)
      const now = new Date();
      const defaultTitle = `Reunião - ${now.toLocaleDateString('pt-BR')} ${now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
      const title = (meetingTitleInput.value && meetingTitleInput.value.trim()) || defaultTitle;

      // 1. Criar reunião no backend
      const meetingRes = await fetch('/meetings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });

      if (!meetingRes.ok) {
        throw new Error(`Erro ao criar reunião: status ${meetingRes.status}`);
      }
      const meetingData = await meetingRes.json();
      currentMeetingId = meetingData.id;

      // 2. Upload do arquivo de áudio gravado
      const formData = new FormData();
      const ext = mimeType.includes('mp4') ? 'm4a' : 'webm';
      const file = new File([blob], `gravacao_reuniao_${currentMeetingId}.${ext}`, { type: mimeType });
      formData.append('file', file);

      const uploadRes = await fetch(`/meetings/${currentMeetingId}/audio`, {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        throw new Error(`Erro no upload de áudio: status ${uploadRes.status}`);
      }

      // 3. Iniciar processamento da reunião
      processingStatusText.textContent = 'Iniciando pipeline de IA (transcrição e sumarização)...';
      updatePipelineStep('transcribing');

      const processRes = await fetch(`/meetings/${currentMeetingId}/process`, {
        method: 'POST',
      });

      if (!processRes.ok && processRes.status !== 202) {
        throw new Error(`Erro ao iniciar processamento: status ${processRes.status}`);
      }

      // 4. Polling do status até completar
      startStatusPolling(currentMeetingId, title);

    } catch (err) {
      showToast(err.message, true);
      processingSection.style.display = 'none';
      recordIdlePanel.style.display = 'block';
    } finally {
      btnStop.disabled = false;
      btnStop.textContent = 'Finalizar e Gerar Resumo';
    }
  });

  // Atualiza indicadores visuais do pipeline
  function updatePipelineStep(step) {
    [stepReceived, stepUploaded, stepTranscribing, stepSummarizing, stepCompleted].forEach((el) => {
      if (el) el.classList.remove('active');
    });

    if (step === 'received') {
      stepReceived?.classList.add('active');
    } else if (step === 'uploaded') {
      stepReceived?.classList.add('completed');
      stepUploaded?.classList.add('active');
    } else if (step === 'transcribing') {
      stepReceived?.classList.add('completed');
      stepUploaded?.classList.add('completed');
      stepTranscribing?.classList.add('active');
    } else if (step === 'summarizing') {
      stepReceived?.classList.add('completed');
      stepUploaded?.classList.add('completed');
      stepTranscribing?.classList.add('completed');
      stepSummarizing?.classList.add('active');
    } else if (step === 'completed') {
      stepReceived?.classList.add('completed');
      stepUploaded?.classList.add('completed');
      stepTranscribing?.classList.add('completed');
      stepSummarizing?.classList.add('completed');
      stepCompleted?.classList.add('completed');
    }
  }

  // Polling de status
  function startStatusPolling(meetingId, title) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`/meetings/${meetingId}/status`);
        if (!res.ok) return;

        const data = await res.json();
        const status = data.status;

        if (status === 'audio_uploaded') {
          updatePipelineStep('uploaded');
          processingStatusText.textContent = 'Áudio carregado com sucesso. Aguardando fila...';
        } else if (status === 'transcribing') {
          updatePipelineStep('transcribing');
          processingStatusText.textContent = 'Transcrevendo fala em texto com Inteligência Artificial...';
        } else if (status === 'transcribed' || status === 'summarizing' || status === 'processing') {
          updatePipelineStep('summarizing');
          processingStatusText.textContent = 'Gerando resumo executivo, identificando pontos-chave e extraindo tarefas...';
        } else if (status === 'completed') {
          clearInterval(pollingInterval);
          pollingInterval = null;
          updatePipelineStep('completed');
          processingStatusText.textContent = 'Reunião processada com sucesso!';
          setTimeout(() => {
            loadMeetingDetails(meetingId, title);
            fetchRecentMeetings();
          }, 600);
        } else if (status === 'failed') {
          clearInterval(pollingInterval);
          pollingInterval = null;
          showToast(`Falha no processamento: ${data.error_message || 'Erro desconhecido'}`, true);
          processingSection.style.display = 'none';
          recordIdlePanel.style.display = 'block';
        }
      } catch (err) {
        console.error('Erro no polling:', err);
      }
    }, 2500);
  }

  // Carrega e exibe o resultado final
  async function loadMeetingDetails(meetingId, title) {
    processingSection.style.display = 'none';
    resultSection.style.display = 'block';

    resultTitle.textContent = title || `Reunião #${meetingId}`;
    resultStatus.textContent = 'Concluída';
    resultStatus.className = 'status-badge status-completed';

    // 1. Carrega Resumo
    try {
      const summaryRes = await fetch(`/meetings/${meetingId}/summary`);
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        summaryObjective.textContent = summaryData.objective || 'Não informado';
        summaryContent.textContent = summaryData.summary || 'Sem resumo disponível';

        // Pontos-chave
        summaryKeyPoints.innerHTML = '';
        if (summaryData.key_points && summaryData.key_points.length > 0) {
          summaryData.key_points.forEach((pt) => {
            const li = document.createElement('li');
            li.textContent = pt;
            summaryKeyPoints.appendChild(li);
          });
        } else {
          summaryKeyPoints.innerHTML = '<li>Nenhum ponto chave destacado.</li>';
        }

        // Decisões
        summaryDecisions.innerHTML = '';
        if (summaryData.decisions && summaryData.decisions.length > 0) {
          summaryData.decisions.forEach((dec) => {
            const li = document.createElement('li');
            li.textContent = dec;
            summaryDecisions.appendChild(li);
          });
        } else {
          summaryDecisions.innerHTML = '<li>Nenhuma decisão registrada.</li>';
        }

        // Tarefas
        taskList.innerHTML = '';
        if (summaryData.tasks && summaryData.tasks.length > 0) {
          summaryData.tasks.forEach((t) => {
            const div = document.createElement('li');
            div.className = 'task-item';
            div.innerHTML = `
              <div>
                <strong>${t.description}</strong>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                  ${t.assignee ? `<span>👤 ${t.assignee}</span> • ` : ''}
                  ${t.due_date ? `<span>📅 Prazo: ${t.due_date}</span> • ` : ''}
                  <span>Status: ${t.status || 'pendente'}</span>
                </div>
              </div>
            `;
            taskList.appendChild(div);
          });
        } else {
          taskList.innerHTML = '<li style="color: var(--text-muted);">Nenhuma tarefa pendente identificada.</li>';
        }
      }
    } catch (e) {
      console.warn('Não foi possível carregar o resumo:', e);
    }

    // 2. Carrega Transcrição
    try {
      const transcriptRes = await fetch(`/meetings/${meetingId}/transcript`);
      if (transcriptRes.ok) {
        const transcriptData = await transcriptRes.json();
        transcriptList.innerHTML = '';

        if (transcriptData.segments && transcriptData.segments.length > 0) {
          transcriptData.segments.forEach((seg) => {
            const segDiv = document.createElement('div');
            segDiv.className = 'transcript-segment';
            const speaker = seg.speaker || 'Participante';
            segDiv.innerHTML = `
              <div class="speaker-tag">${speaker} <span style="font-weight: 400; color: var(--text-muted);">(${Math.round(seg.start_time)}s - ${Math.round(seg.end_time)}s)</span></div>
              <div>${seg.text}</div>
            `;
            transcriptList.appendChild(segDiv);
          });
        } else if (transcriptData.content) {
          transcriptList.innerHTML = `<div class="transcript-segment">${transcriptData.content}</div>`;
        } else {
          transcriptList.innerHTML = '<div style="color: var(--text-muted);">Transcrição vazia.</div>';
        }
      }
    } catch (e) {
      console.warn('Não foi possível carregar a transcrição:', e);
    }
  }

  // Abas de resultado
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBtns.forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('active'));
      
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.add('active');
    });
  });

  // Botão Nova Gravação
  btnNewRecording.addEventListener('click', () => {
    resetToIdle();
  });

  function resetToIdle() {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    if (pollingInterval) clearInterval(pollingInterval);
    timerDisplay.textContent = '00:00';
    if (micVuBar) micVuBar.style.width = '0%';
    if (systemVuBar) systemVuBar.style.width = '0%';
    if (meetingTitleInput) meetingTitleInput.value = '';
    
    recordingActivePanel.style.display = 'none';
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    recordIdlePanel.style.display = 'block';
  }

  // Carregar histórico de reuniões recentes
  async function fetchRecentMeetings() {
    if (!recentMeetingsContainer) return;
    try {
      const res = await fetch('/meetings');
      if (!res.ok) return;

      const meetings = await res.json();
      recentMeetingsContainer.innerHTML = '';

      if (!meetings || meetings.length === 0) {
        recentMeetingsContainer.innerHTML = '<div style="color: var(--text-muted); grid-column: 1/-1;">Nenhuma reunião gravada ainda.</div>';
        return;
      }

      meetings.slice(-6).reverse().forEach((m) => {
        const card = document.createElement('div');
        card.className = 'meeting-card';
        const dateStr = m.created_at ? new Date(m.created_at).toLocaleDateString('pt-BR') : '';
        const badgeClass = m.status === 'completed' ? 'status-completed' : (m.status === 'failed' ? 'status-failed' : 'status-processing');

        card.innerHTML = `
          <div class="meeting-card-title">${m.title || `Reunião #${m.id}`}</div>
          <div class="meeting-card-meta">
            <span>${dateStr}</span>
            <span class="status-badge ${badgeClass}">${m.status}</span>
          </div>
        `;
        card.addEventListener('click', () => {
          loadMeetingDetails(m.id, m.title);
        });
        recentMeetingsContainer.appendChild(card);
      });
    } catch (err) {
      console.warn('Erro ao listar reuniões recentes:', err);
    }
  }

  // Verifica autenticação e carrega dados do usuário
  checkAuth();
});
