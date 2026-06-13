import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth-service';

@Component({
  selector: 'app-first-login',
  imports: [CommonModule, FormsModule],
  templateUrl: './first-login.html',
  styleUrl: './first-login.css',
})
export class FirstLogin implements OnInit {
  authService = inject(AuthService);
  router = inject(Router);
  cdr = inject(ChangeDetectorRef);

  currentStage = 1;
  loading = true;
  saving = false;
  errorMessage = '';
  googleAvatarUrl = '';
  uploadingAvatar = false;
  uploadingResume = false;
  resumeFileName = '';
  
  profile = {
    auth_id: '',
    full_name: '',
    avatar_url: '',
    social_media_url: [] as string[],
    interest_area: [] as string[],
    resume_url: '',
    first_time_login: false
  };

  newSocialUrl = '';
  newInterest = '';

  async ngOnInit() {
    try {
      const user = await this.authService.getUser();
      if (!user) {
        this.router.navigate(['/auth']);
        return;
      }

      this.profile.auth_id = user.id;

      // Extract initial fallback details from Google OAuth metadata
      const metadata = user.user_metadata || {};
      const fallbackName = metadata['full_name'] || user.email?.split('@')[0] || '';
      
      this.profile.full_name = fallbackName;
      this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;
    } catch (err: any) {
      console.error('Error initializing onboarding:', err);
      this.errorMessage = 'Failed to load user details.';
    } finally {
      this.loading = false;
      this.cdr.detectChanges();
    }
  }

  nextStage() {
    this.errorMessage = '';
    if (this.currentStage === 1) {
      if (!this.profile.full_name.trim()) {
        this.errorMessage = 'Full name is required to proceed.';
        return;
      }
    }
    this.currentStage++;
  }

  prevStage() {
    this.errorMessage = '';
    if (this.currentStage > 1) {
      this.currentStage--;
    }
  }

  skipStage() {
    this.errorMessage = '';
    if (this.currentStage === 2) {
      this.currentStage = 3;
    } else if (this.currentStage === 3) {
      this.completeOnboarding();
    }
  }

  async completeOnboarding() {
    this.saving = true;
    this.errorMessage = '';

    try {
      const payload = {
        auth_id: this.profile.auth_id,
        full_name: this.profile.full_name.trim(),
        avatar_url: this.profile.avatar_url.trim() || null,
        social_media_url: this.profile.social_media_url,
        interest_area: this.profile.interest_area,
        resume_url: this.profile.resume_url.trim() || null,
        first_time_login: false
      };

      const { data, error } = await this.authService.supabaseClient
        .from('profiles')
        .insert(payload)
        .select()
        .single();

      if (error) {
        throw error;
      }

      // Successful onboarding! Redirect to marketplace.
      this.router.navigate(['/internal/marketplace']);
    } catch (err: any) {
      console.error('Error saving onboarding profile:', err);
      this.errorMessage = err.message || 'Failed to complete onboarding.';
      this.cdr.detectChanges();
    } finally {
      this.saving = false;
      this.cdr.detectChanges();
    }
  }

  // Social Links Helpers
  addSocial(event?: Event) {
    if (event) {
      event.preventDefault();
    }
    const url = this.newSocialUrl.trim();
    if (url) {
      try {
        new URL(url.startsWith('http') ? url : 'https://' + url);
        if (!this.profile.social_media_url.includes(url)) {
          this.profile.social_media_url.push(url);
        }
        this.newSocialUrl = '';
      } catch (e) {
        this.errorMessage = 'Please enter a valid URL.';
        setTimeout(() => this.errorMessage = '', 3000);
      }
    }
  }

  removeSocial(index: number) {
    this.profile.social_media_url.splice(index, 1);
  }

  getSocialIconClass(url: string): string {
    const lower = url.toLowerCase();
    if (lower.includes('github.com')) return 'bx bxl-github';
    if (lower.includes('linkedin.com')) return 'bx bxl-linkedin-square';
    if (lower.includes('twitter.com') || lower.includes('x.com')) return 'bx bxl-twitter';
    if (lower.includes('facebook.com')) return 'bx bxl-facebook-circle';
    if (lower.includes('instagram.com')) return 'bx bxl-instagram';
    return 'bx bx-link';
  }

  getSocialLabel(url: string): string {
    const lower = url.toLowerCase();
    if (lower.includes('github.com')) return 'GitHub';
    if (lower.includes('linkedin.com')) return 'LinkedIn';
    if (lower.includes('twitter.com') || lower.includes('x.com')) return 'Twitter';
    return url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0];
  }

  // Interest tags helpers
  addInterest(event?: Event) {
    if (event) {
      event.preventDefault();
    }
    const tag = this.newInterest.trim();
    if (tag && !this.profile.interest_area.includes(tag)) {
      this.profile.interest_area.push(tag);
    }
    this.newInterest = '';
  }

  removeInterest(index: number) {
    this.profile.interest_area.splice(index, 1);
  }

  async onAvatarSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    if (!file.type.startsWith('image/')) {
      this.errorMessage = 'Please select an image file (PNG, JPG, GIF, WebP).';
      setTimeout(() => this.errorMessage = '', 3000);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.errorMessage = 'Avatar image must be under 5 MB.';
      setTimeout(() => this.errorMessage = '', 3000);
      return;
    }

    this.uploadingAvatar = true;
    this.errorMessage = '';
    this.cdr.detectChanges();

    try {
      const fileExt = file.name.split('.').pop();
      const fileName = `${this.profile.auth_id}-${Date.now()}.${fileExt}`;

      const { data, error } = await this.authService.supabaseClient.storage
        .from('avatar-bucket')
        .upload(fileName, file, {
          cacheControl: '3600',
          upsert: true
        });

      if (error) throw error;

      const { data: urlData } = this.authService.supabaseClient.storage
        .from('avatar-bucket')
        .getPublicUrl(fileName);

      this.profile.avatar_url = urlData.publicUrl;
    } catch (err: any) {
      console.error('Error uploading avatar:', err);
      this.errorMessage = err.message || 'Failed to upload avatar.';
      this.profile.avatar_url = '';
    } finally {
      this.uploadingAvatar = false;
      this.cdr.detectChanges();
    }
  }

  removeAvatar() {
    this.profile.avatar_url = '';
    this.cdr.detectChanges();
  }

  get displayAvatarUrl(): string {
    return this.profile.avatar_url || this.googleAvatarUrl || 'https://ui-avatars.com/api/?name=User';
  }

  async onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    this.resumeFileName = file.name;
    this.uploadingResume = true;
    this.errorMessage = '';
    this.cdr.detectChanges();

    try {
      const fileExt = file.name.split('.').pop();
      const fileName = `${this.profile.auth_id}-${Date.now()}.${fileExt}`;
      
      const { data, error } = await this.authService.supabaseClient.storage
        .from('resume-bucket')
        .upload(fileName, file, {
          cacheControl: '3600',
          upsert: true
        });

      if (error) {
        throw error;
      }

      const { data: urlData } = this.authService.supabaseClient.storage
        .from('resume-bucket')
        .getPublicUrl(fileName);

      this.profile.resume_url = urlData.publicUrl;
    } catch (err: any) {
      console.error('Error uploading resume:', err);
      this.errorMessage = err.message || 'Failed to upload resume.';
      this.resumeFileName = '';
      this.profile.resume_url = '';
    } finally {
      this.uploadingResume = false;
      this.cdr.detectChanges();
    }
  }

  removeResume() {
    this.profile.resume_url = '';
    this.resumeFileName = '';
    this.cdr.detectChanges();
  }
}
