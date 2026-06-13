import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../services/auth-service';

@Component({
  selector: 'app-meeting-report',
  imports: [CommonModule],
  templateUrl: './meeting-report.html',
  styleUrl: './meeting-report.css',
})
export class MeetingReport implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  userInterviewId: string | null = null;
  interviewTrack: any = null;
  isLoading = true;
  googleAvatarUrl = '';
  userName = 'User';

  reportMarkdown = '';
  reportHtml = '';

  async ngOnInit() {
    this.userInterviewId = this.route.snapshot.paramMap.get('id');

    // 1. Fetch user data
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
      await this.loadReportData();
    } else {
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  async loadReportData() {
    try {
      this.isLoading = true;
      this.cdr.detectChanges();

      // Fetch user_interview record
      const { data: userInterview, error: uiError } = await this.authService.supabaseClient
        .from('user_interview')
        .select('*')
        .eq('id', this.userInterviewId)
        .single();

      if (uiError) throw uiError;

      if (userInterview) {
        // Fetch track metadata
        const { data: track, error: trackError } = await this.authService.supabaseClient
          .from('ai-interview')
          .select('*')
          .eq('id', userInterview.interview_id)
          .single();

        if (trackError) throw trackError;
        this.interviewTrack = track;

        // Download report from supabase storage
        const filePath = `${userInterview.auth_id}/${userInterview.interview_id}.md`;
        console.log('Downloading report from path:', filePath);
        
        const { data: blob, error: storageError } = await this.authService.supabaseClient
          .storage
          .from('ai-interview')
          .download(filePath);

        if (storageError) throw storageError;

        if (blob) {
          this.reportMarkdown = await blob.text();
          this.reportHtml = this.formatMarkdown(this.reportMarkdown);
        }
      }
    } catch (err) {
      console.error('Error loading report data:', err);
      this.reportMarkdown = '# Evaluation Report Load Failed\n\nWe could not retrieve your evaluation report. Please make sure the interview completed successfully and try again later.';
      this.reportHtml = this.formatMarkdown(this.reportMarkdown);
    } finally {
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  formatMarkdown(text: string): string {
    if (!text) return '';
    
    // Safely parse Markdown elements to HTML
    let html = text
      .replace(/^# (.*$)/gim, '<h1 class="report-h1">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="report-h2">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="report-h3">$1</h3>')
      .replace(/^\* (.*$)/gim, '<li class="report-li">$1</li>')
      .replace(/^- (.*$)/gim, '<li class="report-li">$1</li>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="report-strong">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="report-em">$1</em>')
      .replace(/`([^`]+)`/g, '<code class="report-code">$1</code>')
      .replace(/---/g, '<hr class="report-hr">')
      .replace(/\n/g, '<br>');
      
    return html;
  }

  goBackToHub() {
    this.router.navigate(['/internal/ai-interview']);
  }
}
