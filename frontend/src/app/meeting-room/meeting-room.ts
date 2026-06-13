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

  // WebRTC
  private pc: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  webrtcStatus: 'connecting' | 'connected' | 'disconnected' | 'failed' = 'connecting';
  statusMessage = 'Initializing meeting room...';

  // Web Speech API
  private recognition: any = null;
  isRecording = false;
  currentResponseText = '';
  aiSpeechPlaying = false;
  private silenceTimeout: any = null;

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
      await this.setupWebRTC();
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

  async setupWebRTC() {
    try {
      this.webrtcStatus = 'connecting';
      this.statusMessage = 'Connecting to WebRTC gateway...';
      this.cdr.detectChanges();

      this.pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      // Handle ICE Connection State Changes
      this.pc.oniceconnectionstatechange = () => {
        if (!this.pc) return;
        const state = this.pc.iceConnectionState;
        console.log('WebRTC ICE State:', state);
        if (state === 'connected') {
          this.webrtcStatus = 'connected';
          this.statusMessage = 'Connected. Waiting for AI...';
        } else if (state === 'disconnected') {
          this.webrtcStatus = 'disconnected';
          this.statusMessage = 'Disconnected from server.';
        } else if (state === 'failed') {
          this.webrtcStatus = 'failed';
          this.statusMessage = 'Connection failed. Please retry.';
        }
        this.cdr.detectChanges();
      };

      // Create DataChannel (Client-side initiated)
      this.dataChannel = this.pc.createDataChannel('chat');
      this.setupDataChannelListeners();

      // Create offer
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);

      // Wait for complete ICE gathering
      await new Promise<void>((resolve) => {
        if (!this.pc) return resolve();
        if (this.pc.iceGatheringState === 'complete') {
          resolve();
        } else {
          const checkState = () => {
            if (this.pc && this.pc.iceGatheringState === 'complete') {
              this.pc.removeEventListener('icegatheringstatechange', checkState);
              resolve();
            }
          };
          this.pc.addEventListener('icegatheringstatechange', checkState);
        }
      });

      // Post offer to Python Backend
      const offerPayload = {
        sdp: this.pc.localDescription?.sdp || '',
        type: this.pc.localDescription?.type || 'offer',
        user_interview_id: this.userInterviewId
      };

      const response = await fetch(`${environment.backendUrl}/api/v1/webrtc/offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(offerPayload)
      });

      if (!response.ok) {
        throw new Error(`Signaling server error: ${response.statusText}`);
      }

      const answer = await response.json();
      await this.pc.setRemoteDescription(new RTCSessionDescription(answer));

    } catch (err: any) {
      console.error('Error negotiating WebRTC connection:', err);
      this.webrtcStatus = 'failed';
      this.statusMessage = `Failed to connect: ${err.message}`;
      this.cdr.detectChanges();
    }
  }

  setupDataChannelListeners() {
    if (!this.dataChannel) return;

    this.dataChannel.onopen = () => {
      console.log('WebRTC Data Channel Open');
      this.statusMessage = 'Session established. Click Start Practice.';
      this.cdr.detectChanges();
      
      // Auto-start session
      this.startInterviewSession();
    };

    this.dataChannel.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received Message from Backend:', data);

        if (data.type === 'status') {
          this.statusMessage = data.message;
          this.cdr.detectChanges();
        } else if (data.type === 'first_question') {
          this.isWaitingForAi = false;
          this.currentQuestionText = data.question;
          this.currentQuestionIndex = data.index;
          this.transcriptMarkdown = data.transcript || '';
          this.walkthroughMarkdown = data.walkthrough || '';
          this.statusMessage = 'Speaking question...';
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
              this.speakText(`Let's move to the next question. ${data.next_question}`, () => {
                this.startRecording();
              });
            } else {
              this.interviewCompleted = true;
              this.currentQuestionText = 'Interview completed. Generating report...';
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
        console.error('Error parsing data channel message:', err);
      }
    };

    this.dataChannel.onclose = () => {
      console.log('WebRTC Data Channel Closed');
      this.webrtcStatus = 'disconnected';
      this.statusMessage = 'Interview session disconnected.';
      this.cdr.detectChanges();
    };
  }

  startInterviewSession() {
    if (this.dataChannel && this.dataChannel.readyState === 'open') {
      this.isWaitingForAi = true;
      this.statusMessage = 'Starting interview session...';
      this.dataChannel.send(JSON.stringify({ type: 'start_session' }));
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
      if (this.silenceTimeout) {
        clearTimeout(this.silenceTimeout);
      }

      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      this.currentResponseText = finalTranscript || interimTranscript;
      this.cdr.detectChanges();

      // Automatically submit the answer when user finishes speaking (2.5 seconds of silence)
      if (this.currentResponseText.trim().length > 0) {
        this.silenceTimeout = setTimeout(() => {
          console.log('Silence detected, auto-submitting answer...');
          this.submitAnswer();
        }, 2500);
      }
    };

    this.recognition.onerror = (event: any) => {
      console.error('SpeechRecognition error:', event.error);
      if (event.error === 'no-speech') {
        this.statusMessage = 'No speech detected. Please speak louder.';
        this.cdr.detectChanges();
      }
    };

    this.recognition.onend = () => {
      this.isRecording = false;
      this.cdr.detectChanges();
    };

    this.recognition.start();
  }

  stopRecording() {
    if (this.recognition && this.isRecording) {
      this.recognition.stop();
      this.isRecording = false;
      this.cdr.detectChanges();
    }
  }

  submitAnswer() {
    this.stopRecording();
    if (this.silenceTimeout) {
      clearTimeout(this.silenceTimeout);
      this.silenceTimeout = null;
    }
    
    if (!this.currentResponseText.trim()) {
      return;
    }

    if (this.dataChannel && this.dataChannel.readyState === 'open') {
      // Cancel speech synthesis if active
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }

      this.isWaitingForAi = true;
      this.statusMessage = 'AI is polishing your response and evaluating...';
      
      this.dataChannel.send(JSON.stringify({
        type: 'user_response',
        text: this.currentResponseText
      }));

      this.currentResponseText = '';
      this.cdr.detectChanges();
    } else {
      alert('WebRTC session is disconnected. Try refreshing.');
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
      }
    }
    this.cdr.detectChanges();
  }

  formatMarkdown(text: string): string {
    if (!text) return '';
    
    // Convert markdown into simple HTML safely
    let html = text
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
    if (this.silenceTimeout) {
      clearTimeout(this.silenceTimeout);
      this.silenceTimeout = null;
    }

    // Close WebRTC connection
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
  }

  ngOnDestroy() {
    this.cleanup();
  }
}
