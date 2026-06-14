import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';

@Component({
  selector: 'app-ai-interview',
  imports: [],
  templateUrl: './ai-interview.html',
  styleUrl: './ai-interview.css',
})
export class AiInterview implements OnInit {
  internal = inject(Internal);
  authService = inject(AuthService);
  router = inject(Router);
  cdr = inject(ChangeDetectorRef);

  googleAvatarUrl = '';
  tracks: any[] = [];
  isNavigating = false;

  async startPractice(track: any) {
    if (this.isNavigating) return;
    try {
      this.isNavigating = true;
      const user = await this.authService.getUser();
      if (!user) {
        alert('Please log in to start a practice session.');
        return;
      }

      // Check if a user_interview record already exists for this user and interview_id
      const { data: existing, error: fetchError } = await this.authService.supabaseClient
        .from('user_interview')
        .select('id')
        .eq('auth_id', user.id)
        .eq('interview_id', track.id)
        .maybeSingle();

      if (fetchError) throw fetchError;

      let interviewRecordId: any;

      if (existing) {
        interviewRecordId = existing.id;
      } else {
        // Create new record
        const { data: inserted, error: insertError } = await this.authService.supabaseClient
          .from('user_interview')
          .insert({
            interview_id: track.id,
            auth_id: user.id,
            interview_completed: false
          })
          .select()
          .single();

        if (insertError) throw insertError;
        interviewRecordId = inserted.id;
      }

      // Navigate to /:id/meeting-lobby
      this.router.navigate([`/${interviewRecordId}/meeting-lobby`]);
    } catch (err) {
      console.error('Error starting practice session:', err);
      alert('Failed to start practice session. Please try again.');
    } finally {
      this.isNavigating = false;
      this.cdr.detectChanges();
    }
  }

  async ngOnInit() {
    try {
      const user = await this.authService.getUser();
      if (user) {
        const metadata = user.user_metadata || {};
        const fallbackName = metadata['full_name'] || user.email?.split('@')[0] || 'User';
        this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;
      }
      await this.loadTracks();
    } catch (err) {
      console.error('Error fetching user metadata in ai-interview:', err);
    } finally {
      this.cdr.detectChanges();
    }
  }

  async loadTracks() {
    try {
      const { data, error } = await this.authService.supabaseClient
        .from('ai-interview')
        .select('*')
        .order('id', { ascending: true });
      if (error) throw error;
      this.tracks = data || [];
    } catch (err) {
      console.error('Error loading interview tracks:', err);
    }
  }

  getTrackIcon(title: string): string {
    const lowerTitle = title.toLowerCase();
    if (lowerTitle.includes('engineering') || lowerTitle.includes('it') || lowerTitle.includes('code')) {
      return 'bx bx-code-block';
    }
    if (lowerTitle.includes('business') || lowerTitle.includes('strategy') || lowerTitle.includes('chart')) {
      return 'bx bx-line-chart';
    }
    if (lowerTitle.includes('marketing') || lowerTitle.includes('growth') || lowerTitle.includes('megaphone')) {
      return 'bx bx-megaphone';
    }
    if (lowerTitle.includes('data') || lowerTitle.includes('science') || lowerTitle.includes('sql')) {
      return 'bx bx-data';
    }
    if (lowerTitle.includes('leadership') || lowerTitle.includes('hr') || lowerTitle.includes('group')) {
      return 'bx bx-group';
    }
    return 'bx bx-book-open';
  }

  getTrackIconClass(title: string): string {
    const lowerTitle = title.toLowerCase();
    if (lowerTitle.includes('engineering') || lowerTitle.includes('it') || lowerTitle.includes('code')) {
      return 'icon-box bg-blue';
    }
    if (lowerTitle.includes('business') || lowerTitle.includes('strategy') || lowerTitle.includes('chart')) {
      return 'icon-box bg-white shadow-icon';
    }
    if (lowerTitle.includes('marketing') || lowerTitle.includes('growth') || lowerTitle.includes('megaphone')) {
      return 'icon-box bg-green';
    }
    if (lowerTitle.includes('data') || lowerTitle.includes('science') || lowerTitle.includes('sql')) {
      return 'icon-box bg-teal';
    }
    if (lowerTitle.includes('leadership') || lowerTitle.includes('hr') || lowerTitle.includes('group')) {
      return 'icon-box bg-red';
    }
    return 'icon-box bg-blue';
  }
}
