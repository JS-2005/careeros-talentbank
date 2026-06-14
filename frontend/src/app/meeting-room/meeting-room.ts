import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../services/auth-service';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-meeting-room',
  imports: [CommonModule, FormsModule],
  templateUrl: './meeting-room.html',
  styleUrl: './meeting-room.css',
})
export class MeetingRoom implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  userInterviewId: string | null = null;
  interviewTrack: any = null;
  isLoading = true;
  googleAvatarUrl = '';
  userName = 'User';

  // SSE Connection
  private eventSource: EventSource | null = null;
  webrtcStatus: 'connecting' | 'connected' | 'disconnected' | 'failed' = 'connecting';
  statusMessage = 'Initializing meeting room...';

  // Web Speech API
  private recognition: any = null;
  isRecording = false;
  currentResponseText = '';
  accumulatedTranscript = '';
  shouldBeRecording = false;
  aiSpeechPlaying = false;

  // Local media stream
  isVideoOn = true;
  isMicOn = true;
  stream: MediaStream | null = null;

  // Tabs for the side panel
  activeTab: 'transcript' | 'walkthrough' = 'transcript';

  // Content for the side panel (Markdown text)
  transcriptMarkdown = '';
  walkthroughMarkdown = '';

  // Interview state
  currentQuestionText = 'Welcome! The AI interviewer is preparing the first question...';
  currentQuestionIndex = 0;
  totalQuestions = 3;
  isWaitingForAi = false;
  interviewCompleted = false;

  // Diagram Drawing Board State
  showDiagramTool = false;
  drawingMode: 'pencil' | 'line' | 'rect' | 'circle' | 'text' | 'eraser' = 'pencil';
  strokeColor = '#3b82f6';
  strokeWidth = 3;
  colors: string[] = ['#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899', '#ffffff', '#1f2937'];
  undoStack: ImageData[] = [];
  hasDrawing = false;

  // Text Tool Specifics
  showTextInput = false;
  textInputX = 0;
  textInputY = 0;
  textInputValue = '';
  private textStartX = 0;
  private textStartY = 0;

  // Drawing mouse track
  private isDrawing = false;
  private startX = 0;
  private startY = 0;
  private canvasElement: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;

  constructor() {
    // Warm up the speech synthesis voices
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
      };
    }
  }

  async ngOnInit() {
    this.userInterviewId = this.route.snapshot.paramMap.get('id');

    // 1. Fetch user data and interview track
    try {
      const user = await this.authService.getUser();
      if (user) {
        const metadata = user.user_metadata || {};
        this.userName = metadata['full_name'] || user.email?.split('@')[0] || 'User';
        this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(this.userName)}`;
      }
    } catch (err) {
      console.error('Error fetching user metadata:', err);
    }

    if (this.userInterviewId) {
      await this.loadInterviewData();
      await this.startCamera();
      this.setupSSE();
    } else {
      this.statusMessage = 'No interview ID found.';
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  async loadInterviewData() {
    try {
      // Fetch user_interview record
      const { data: userInterview, error: uiError } = await this.authService.supabaseClient
        .from('user_interview')
        .select('*')
        .eq('id', this.userInterviewId)
        .single();

      if (uiError) throw uiError;

      if (userInterview) {
        // Fetch corresponding track metadata
        const { data: track, error: trackError } = await this.authService.supabaseClient
          .from('ai-interview')
          .select('*')
          .eq('id', userInterview.interview_id)
          .single();

        if (trackError) throw trackError;
        this.interviewTrack = track;
        if (track && track.interview_question) {
          this.totalQuestions = track.interview_question.length;
        }
      }

      // Initialize markdown logs from server files if any exist
      const response = await fetch(`${environment.backendUrl}/api/v1/meeting-room/files`);
      if (response.ok) {
        const data = await response.json();
        this.transcriptMarkdown = data.transcript || '';
        this.walkthroughMarkdown = data.walkthrough || '';
      }
    } catch (err) {
      console.error('Error loading interview data:', err);
    } finally {
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  async startCamera() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: true
      });
      this.isVideoOn = true;
      this.isMicOn = true;

      setTimeout(() => {
        const videoElement = document.getElementById('meeting-video-preview') as HTMLVideoElement;
        if (videoElement && this.stream) {
          videoElement.srcObject = this.stream;
        }
      }, 100);
    } catch (err) {
      console.warn('Could not start video/audio:', err);
      this.isVideoOn = false;
      this.isMicOn = false;
    }
    this.cdr.detectChanges();
  }

  setupSSE() {
    this.webrtcStatus = 'connecting';
    this.statusMessage = 'Connecting to interview server...';
    this.cdr.detectChanges();

    const sseUrl = `${environment.backendUrl}/api/v1/interview/events/${this.userInterviewId}`;
    this.eventSource = new EventSource(sseUrl);

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received SSE Message:', data);

        if (data.type === 'connected') {
          this.webrtcStatus = 'connected';
          this.statusMessage = 'Connected. Starting session...';
          this.cdr.detectChanges();
          // Auto-start session once SSE is connected
          this.startInterviewSession();
        } else if (data.type === 'status') {
          this.statusMessage = data.message;
          this.cdr.detectChanges();
        } else if (data.type === 'first_question') {
          this.isWaitingForAi = false;
          this.currentQuestionText = data.question;
          this.currentQuestionIndex = data.index;
          this.transcriptMarkdown = data.transcript || '';
          this.walkthroughMarkdown = data.walkthrough || '';
          this.statusMessage = 'Speaking question...';

          // Handle diagram tool auto popup
          const isDiag = data.diagram_tool || false;
          this.toggleDiagramTool(isDiag);

          this.cdr.detectChanges();

          // Read introduction and the first question
          this.speakText(data.greeting + ' ' + data.question, () => {
            this.startRecording();
          });
        } else if (data.type === 'ai_reply') {
          this.isWaitingForAi = false;
          this.transcriptMarkdown = data.transcript || '';
          this.walkthroughMarkdown = data.walkthrough || '';
          this.statusMessage = 'Speaking feedback...';
          this.cdr.detectChanges();

          this.speakText(data.text, () => {
            if (data.next_question) {
              this.currentQuestionText = data.next_question;
              this.currentQuestionIndex = data.next_index;

              // Handle diagram tool auto popup
              const isDiag = data.diagram_tool || false;
              this.toggleDiagramTool(isDiag);

              this.speakText(`Let's move to the next question. ${data.next_question}`, () => {
                this.startRecording();
              });
            } else {
              this.interviewCompleted = true;
              this.currentQuestionText = 'Interview completed. Generating report...';
              // Hide diagram tool if still open
              this.toggleDiagramTool(false);
              this.speakText('This concludes our interview. Thank you for your time.', () => {
                this.statusMessage = 'Generating report...';
              });
            }
            this.cdr.detectChanges();
          });
        } else if (data.type === 'report_ready') {
          this.isWaitingForAi = false;
          this.statusMessage = 'Report generated successfully! Navigating...';
          this.cdr.detectChanges();
          setTimeout(() => {
            this.cleanup();
            this.router.navigate([`/${this.userInterviewId}/meeting-report`]);
          }, 1500);
        } else if (data.type === 'error') {
          this.statusMessage = `Error: ${data.message}`;
          this.isWaitingForAi = false;
          this.cdr.detectChanges();
        }
      } catch (err) {
        console.error('Error parsing SSE message:', err);
      }
    };

    this.eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
      this.webrtcStatus = 'disconnected';
      this.statusMessage = 'Disconnected from server. Reconnecting...';
      this.cdr.detectChanges();
    };
  }

  async startInterviewSession() {
    try {
      this.isWaitingForAi = true;
      this.statusMessage = 'Starting interview session...';
      this.cdr.detectChanges();

      const response = await fetch(`${environment.backendUrl}/api/v1/interview/start-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_interview_id: this.userInterviewId })
      });

      if (!response.ok) {
        throw new Error(`Failed to start session: ${response.statusText}`);
      }
    } catch (err: any) {
      console.error('Error starting interview session:', err);
      this.statusMessage = `Failed to start: ${err.message}`;
      this.isWaitingForAi = false;
      this.cdr.detectChanges();
    }
  }

  // Voice Interaction (TTS)
  speakText(text: string, callback?: () => void) {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      if (callback) callback();
      return;
    }

    // Cancel current speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    
    // Choose voice
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => 
      voice.name.includes('Google US English') || 
      voice.name.includes('Natural') ||
      voice.lang.startsWith('en-US')
    );
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
      this.aiSpeechPlaying = true;
      this.cdr.detectChanges();
    };

    utterance.onend = () => {
      this.aiSpeechPlaying = false;
      this.cdr.detectChanges();
      if (callback) {
        callback();
      }
    };

    utterance.onerror = (e) => {
      console.error('SpeechSynthesis error:', e);
      this.aiSpeechPlaying = false;
      this.cdr.detectChanges();
      if (callback) {
        callback();
      }
    };

    window.speechSynthesis.speak(utterance);
  }

  // Speech Recognition (STT)
  startRecording() {
    if (this.isRecording) return;
    
    this.shouldBeRecording = true;
    
    if (!this.recognition) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        this.statusMessage = 'Speech recognition not supported in this browser.';
        this.cdr.detectChanges();
        return;
      }

      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        this.isRecording = true;
        this.statusMessage = 'Listening... Please speak your answer.';
        this.cdr.detectChanges();
      };

      this.recognition.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        const currentSessionText = finalTranscript || interimTranscript;
        this.currentResponseText = (this.accumulatedTranscript + ' ' + currentSessionText).trim();
        this.cdr.detectChanges();
      };

      this.recognition.onerror = (event: any) => {
        console.error('SpeechRecognition error:', event.error);
        if (event.error === 'no-speech') {
          this.statusMessage = 'No speech detected. Please speak louder.';
          this.cdr.detectChanges();
        }
      };

      this.recognition.onend = () => {
        if (this.shouldBeRecording && this.isMicOn) {
          console.log('Speech recognition ended. Restarting...');
          this.accumulatedTranscript = this.currentResponseText;
          
          setTimeout(() => {
            try {
              if (this.shouldBeRecording && this.isMicOn) {
                this.recognition.start();
              }
            } catch (err) {
              console.error('Failed to restart speech recognition:', err);
            }
          }, 100);
        } else {
          this.isRecording = false;
          this.cdr.detectChanges();
        }
      };
    }

    if (this.isMicOn) {
      try {
        this.recognition.start();
      } catch (err) {}
    } else {
      this.statusMessage = 'Mic is muted. Unmute to speak your answer.';
      this.cdr.detectChanges();
    }
  }

  stopRecording() {
    this.shouldBeRecording = false;
    if (this.recognition && this.isRecording) {
      this.recognition.stop();
      this.isRecording = false;
      this.cdr.detectChanges();
    }
  }

  async submitAnswer() {
    this.stopRecording();

    if (!this.currentResponseText.trim()) {
      return;
    }

    // Cancel speech synthesis if active
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    this.isWaitingForAi = true;
    this.statusMessage = 'AI is polishing your response and evaluating...';

    try {
      const response = await fetch(`${environment.backendUrl}/api/v1/interview/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_interview_id: this.userInterviewId,
          text: this.currentResponseText
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to submit answer: ${response.statusText}`);
      }

      this.currentResponseText = '';
      this.accumulatedTranscript = '';
      this.cdr.detectChanges();
    } catch (err: any) {
      console.error('Error submitting answer:', err);
      alert('Failed to send response. Try refreshing.');
      this.isWaitingForAi = false;
      this.cdr.detectChanges();
    }
  }

  toggleCamera() {
    if (this.stream) {
      const videoTracks = this.stream.getVideoTracks();
      if (videoTracks.length > 0) {
        const newTrackState = !videoTracks[0].enabled;
        videoTracks.forEach(track => track.enabled = newTrackState);
        this.isVideoOn = newTrackState;
      }
    }
    this.cdr.detectChanges();
  }

  toggleMic() {
    if (this.stream) {
      const audioTracks = this.stream.getAudioTracks();
      if (audioTracks.length > 0) {
        const newTrackState = !audioTracks[0].enabled;
        audioTracks.forEach(track => track.enabled = newTrackState);
        this.isMicOn = newTrackState;
        
        if (!newTrackState) {
          if (this.recognition && this.isRecording) {
            this.recognition.stop();
          }
        } else {
          if (this.shouldBeRecording && !this.isRecording) {
            this.startRecording();
          }
        }
      }
    }
    this.cdr.detectChanges();
  }

  formatMarkdown(text: string): string {
    if (!text) return '';
    
    // Format image tags first
    let formattedText = text.replace(/!\[(.*?)\]\((.*?)\)/g, '<div class="md-image-container"><img class="md-image" src="$2" alt="$1"></div>');
    
    // Convert markdown into simple HTML safely
    let html = formattedText
      .replace(/^# (.*$)/gim, '<h1 class="md-h1">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="md-h2">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="md-h3">$1</h3>')
      .replace(/^\* (.*$)/gim, '<li class="md-li">$1</li>')
      .replace(/^- (.*$)/gim, '<li class="md-li">$1</li>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="md-strong">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="md-em">$1</em>')
      .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
      .replace(/---/g, '<hr class="md-hr">')
      .replace(/\n/g, '<br>');
      
    return html;
  }

  leaveInterview() {
    if (confirm('Are you sure you want to end the interview? Progress will be saved.')) {
      this.cleanup();
      this.router.navigate(['/internal/ai-interview']);
    }
  }

  cleanup() {
    this.showDiagramTool = false;
    this.shouldBeRecording = false;
    this.accumulatedTranscript = '';

    // Stop local media tracks
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }

    // Cancel speech
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    // Close speech recognition
    this.stopRecording();

    // Close SSE connection
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  // Diagram Board Interactions and Canvas Helpers
  toggleDiagramTool(show: boolean) {
    this.showDiagramTool = show;
    this.cdr.detectChanges();
    if (show) {
      setTimeout(() => {
        this.initCanvas();
      }, 200);
    }
  }

  initCanvas() {
    this.canvasElement = document.getElementById('diagram-canvas') as HTMLCanvasElement;
    if (!this.canvasElement) {
      console.warn('Canvas element not found!');
      return;
    }
    this.ctx = this.canvasElement.getContext('2d');
    if (!this.ctx) {
      console.warn('Could not get 2D context');
      return;
    }

    const container = document.getElementById('canvas-container-wrapper');
    const containerWidth = container ? container.clientWidth - 40 : 800;
    const containerHeight = container ? container.clientHeight - 40 : 500;
    
    this.canvasElement.width = Math.max(containerWidth, 750);
    this.canvasElement.height = Math.max(containerHeight, 480);

    this.clearCanvasAndDrawGrid();
    
    this.undoStack = [];
    this.hasDrawing = false;
    this.isDrawing = false;
    this.showTextInput = false;
    
    this.saveCanvasState();
    this.cdr.detectChanges();
  }

  clearCanvasAndDrawGrid() {
    if (!this.ctx || !this.canvasElement) return;
    const w = this.canvasElement.width;
    const h = this.canvasElement.height;

    this.ctx.fillStyle = '#ffffff';
    this.ctx.fillRect(0, 0, w, h);

    this.ctx.strokeStyle = '#f1f5f9';
    this.ctx.lineWidth = 1;
    const gridSpacing = 20;

    for (let x = 0; x < w; x += gridSpacing) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, h);
      this.ctx.stroke();
    }
    for (let y = 0; y < h; y += gridSpacing) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(w, y);
      this.ctx.stroke();
    }
  }

  saveCanvasState() {
    if (!this.ctx || !this.canvasElement) return;
    if (this.undoStack.length >= 20) {
      this.undoStack.shift();
    }
    this.undoStack.push(this.ctx.getImageData(0, 0, this.canvasElement.width, this.canvasElement.height));
  }

  getEventCoords(e: any): { x: number, y: number } {
    if (!this.canvasElement) return { x: 0, y: 0 };
    const rect = this.canvasElement.getBoundingClientRect();
    
    let clientX = 0;
    let clientY = 0;
    
    if (e.touches && e.touches.length > 0) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }
    
    return {
      x: clientX - rect.left,
      y: clientY - rect.top
    };
  }

  onCanvasMouseDown(e: any) {
    if (e.cancelable) e.preventDefault();
    if (!this.ctx || !this.canvasElement) return;

    if (this.showTextInput) {
      this.commitTextInput();
      return;
    }

    const coords = this.getEventCoords(e);
    this.startX = coords.x;
    this.startY = coords.y;

    if (this.drawingMode === 'text') {
      this.textStartX = coords.x;
      this.textStartY = coords.y;
      
      const containerRect = document.getElementById('canvas-container-wrapper')?.getBoundingClientRect();
      const canvasRect = this.canvasElement.getBoundingClientRect();
      
      this.textInputX = canvasRect.left - (containerRect?.left || 0) + coords.x;
      this.textInputY = canvasRect.top - (containerRect?.top || 0) + coords.y - 12;
      
      this.textInputValue = '';
      this.showTextInput = true;
      this.cdr.detectChanges();
      
      setTimeout(() => {
        const input = document.getElementById('diagram-text-input') as HTMLInputElement;
        if (input) input.focus();
      }, 50);
      return;
    }

    this.isDrawing = true;
    this.saveCanvasState();
    
    this.ctx.strokeStyle = this.strokeColor;
    this.ctx.lineWidth = this.strokeWidth;
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';

    if (this.drawingMode === 'pencil') {
      this.ctx.beginPath();
      this.ctx.moveTo(coords.x, coords.y);
    } else if (this.drawingMode === 'eraser') {
      this.ctx.save();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = this.strokeWidth * 4;
      this.ctx.beginPath();
      this.ctx.moveTo(coords.x, coords.y);
    }
  }

  onCanvasMouseMove(e: any) {
    if (!this.isDrawing || !this.ctx || !this.canvasElement) return;
    if (e.cancelable) e.preventDefault();

    const coords = this.getEventCoords(e);

    if (this.drawingMode === 'pencil' || this.drawingMode === 'eraser') {
      this.ctx.lineTo(coords.x, coords.y);
      this.ctx.stroke();
      this.hasDrawing = true;
    } else {
      this.restoreLastSavedState();
      
      this.ctx.strokeStyle = this.strokeColor;
      this.ctx.lineWidth = this.strokeWidth;
      this.ctx.lineCap = 'round';
      
      if (this.drawingMode === 'line') {
        this.ctx.beginPath();
        this.ctx.moveTo(this.startX, this.startY);
        this.ctx.lineTo(coords.x, coords.y);
        this.ctx.stroke();
        this.hasDrawing = true;
      } else if (this.drawingMode === 'rect') {
        const w = coords.x - this.startX;
        const h = coords.y - this.startY;
        this.ctx.beginPath();
        this.ctx.rect(this.startX, this.startY, w, h);
        this.ctx.stroke();
        this.hasDrawing = true;
      } else if (this.drawingMode === 'circle') {
        const dx = coords.x - this.startX;
        const dy = coords.y - this.startY;
        const radius = Math.sqrt(dx * dx + dy * dy);
        this.ctx.beginPath();
        this.ctx.arc(this.startX, this.startY, radius, 0, 2 * Math.PI);
        this.ctx.stroke();
        this.hasDrawing = true;
      }
    }
  }

  onCanvasMouseUp(e: any) {
    if (!this.isDrawing) return;
    this.isDrawing = false;
    
    if (this.drawingMode === 'eraser' && this.ctx) {
      this.ctx.restore();
    }
    
    this.saveCanvasState();
    this.cdr.detectChanges();
  }

  restoreLastSavedState() {
    if (!this.ctx || !this.canvasElement || this.undoStack.length === 0) return;
    const lastState = this.undoStack[this.undoStack.length - 1];
    this.ctx.putImageData(lastState, 0, 0);
  }

  undoLastDrawing() {
    if (!this.ctx || !this.canvasElement || this.undoStack.length <= 1) {
      this.clearCanvasAndDrawGrid();
      this.undoStack = [];
      this.saveCanvasState();
      this.hasDrawing = false;
      this.cdr.detectChanges();
      return;
    }
    this.undoStack.pop();
    const previousState = this.undoStack[this.undoStack.length - 1];
    this.ctx.putImageData(previousState, 0, 0);
    this.cdr.detectChanges();
  }

  clearDrawingCanvas() {
    if (confirm('Are you sure you want to clear the entire canvas?')) {
      this.clearCanvasAndDrawGrid();
      this.undoStack = [];
      this.saveCanvasState();
      this.hasDrawing = false;
      this.cdr.detectChanges();
    }
  }

  setDrawingMode(mode: 'pencil' | 'line' | 'rect' | 'circle' | 'text' | 'eraser') {
    this.drawingMode = mode;
    this.showTextInput = false;
    this.cdr.detectChanges();
  }

  setStrokeColor(color: string) {
    this.strokeColor = color;
    this.cdr.detectChanges();
  }

  setStrokeWidth(width: number) {
    this.strokeWidth = width;
    this.cdr.detectChanges();
  }

  commitTextInput() {
    if (!this.showTextInput) return;
    this.showTextInput = false;

    if (this.textInputValue.trim() && this.ctx) {
      this.saveCanvasState();
      
      this.ctx.fillStyle = this.strokeColor;
      this.ctx.font = 'bold 16px sans-serif';
      this.ctx.textBaseline = 'top';
      this.ctx.fillText(this.textInputValue, this.textStartX, this.textStartY);
      
      this.hasDrawing = true;
      this.saveCanvasState();
    }
    
    this.textInputValue = '';
    this.cdr.detectChanges();
  }

  async uploadDiagram(): Promise<string | null> {
    if (!this.canvasElement || !this.hasDrawing) return null;
    
    try {
      const blob = await new Promise<Blob | null>((resolve) => {
        this.canvasElement?.toBlob((b) => resolve(b), 'image/png');
      });
      
      if (!blob) throw new Error('Blob creation failed');
      
      const fileId = `${Math.random().toString(36).substring(2)}-${Date.now()}.png`;
      const path = `diagrams/${this.userInterviewId}/${fileId}`;
      
      const { data, error } = await this.authService.supabaseClient.storage
        .from('ai-interview')
        .upload(path, blob, {
          contentType: 'image/png',
          upsert: true
        });
        
      if (error) throw error;
      
      const { data: publicUrlData } = this.authService.supabaseClient.storage
        .from('ai-interview')
        .getPublicUrl(path);
        
      return publicUrlData.publicUrl;
    } catch (e) {
      console.error('Error uploading diagram to storage:', e);
      return null;
    }
  }

  async submitAnswerWithDiagram() {
    this.stopRecording();
    
    if (!this.hasDrawing) {
      alert('Please draw something on the board first, or click Close to skip.');
      return;
    }

    this.isWaitingForAi = true;
    this.statusMessage = 'Uploading your diagram...';
    this.cdr.detectChanges();

    const diagramUrl = await this.uploadDiagram();
    
    if (!diagramUrl) {
      alert('Failed to upload diagram. Please try again.');
      this.isWaitingForAi = false;
      this.statusMessage = 'Listening... Please speak your answer.';
      this.cdr.detectChanges();
      return;
    }

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    this.isWaitingForAi = true;
    this.statusMessage = 'AI is polishing your response and evaluating...';

    const responseText = this.currentResponseText.trim() || 'See attached diagram for my design solution.';

    try {
      const response = await fetch(`${environment.backendUrl}/api/v1/interview/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_interview_id: this.userInterviewId,
          text: responseText,
          diagram_url: diagramUrl
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to submit: ${response.statusText}`);
      }

      this.showDiagramTool = false;
      this.currentResponseText = '';
      this.accumulatedTranscript = '';
      this.cdr.detectChanges();
    } catch (err: any) {
      console.error('Error submitting answer with diagram:', err);
      alert('Failed to send response. Try refreshing.');
      this.isWaitingForAi = false;
      this.cdr.detectChanges();
    }
  }

  ngOnDestroy() {
    this.cleanup();
  }
}
