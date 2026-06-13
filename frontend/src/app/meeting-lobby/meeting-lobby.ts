import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth-service';

@Component({
  selector: 'app-meeting-lobby',
  imports: [],
  templateUrl: './meeting-lobby.html',
  styleUrl: './meeting-lobby.css',
})
export class MeetingLobby implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  userInterviewId: string | null = null;
  interviewTrack: any = null;
  isLoading = true;
  googleAvatarUrl = '';
  userName = 'User';

  // Camera & Mic settings
  isVideoOn = false;
  isMicOn = false;
  stream: MediaStream | null = null;
  cameraError = '';

  async ngOnInit() {
    // 1. Get user profile metadata
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

    // 2. Fetch interview metadata using route ID
    this.userInterviewId = this.route.snapshot.paramMap.get('id');
    if (this.userInterviewId) {
      await this.loadInterviewData();
    } else {
      this.isLoading = false;
      this.cdr.detectChanges();
    }

    // 3. Request camera / audio access
    await this.startCamera();
  }

  async loadInterviewData() {
    try {
      this.isLoading = true;
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
      this.cameraError = '';
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: true
      });
      this.isVideoOn = true;
      this.isMicOn = true;
      
      // Bind stream to video element
      setTimeout(() => {
        const videoElement = document.getElementById('lobby-video-preview') as HTMLVideoElement;
        if (videoElement && this.stream) {
          videoElement.srcObject = this.stream;
        }
      }, 50);
    } catch (err: any) {
      console.warn('Could not start video/audio preview:', err);
      this.cameraError = 'Could not access camera/microphone. Please check permissions and device connections.';
      this.isVideoOn = false;
      this.isMicOn = false;
    } finally {
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
    } else if (!this.isVideoOn) {
      // Retry starting camera
      this.startCamera();
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

  enterMeetingRoom() {
    if (this.userInterviewId) {
      this.router.navigate([`/${this.userInterviewId}/meeting-room`]);
    }
  }

  goBackToHub() {
    this.router.navigate(['/internal/ai-interview']);
  }

  ngOnDestroy() {
    // Release camera and microphone resource locks
    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        track.stop();
      });
      this.stream = null;
    }
  }
}
