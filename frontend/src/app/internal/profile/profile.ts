import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';

@Component({
  selector: 'app-profile',
  imports: [CommonModule, FormsModule],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class Profile implements OnInit {
  internal = inject(Internal);
  authService = inject(AuthService);
  cdr = inject(ChangeDetectorRef);

  loading = true;
  saving = false;
  isEditMode = false;
  googleAvatarUrl = '';
  uploadingResume = false;
  
  profile: any = {
    id: null,
    auth_id: null,
    full_name: '',
    social_media_url: [] as string[],
    resume_url: '',
    interest_area: [] as string[],
    first_time_login: true
  };

  backupProfile: any = null;
  newInterest = '';
  newSocialUrl = '';
  
  successMessage = '';
  errorMessage = '';

  async ngOnInit() {
    try {
      const currentUser = await this.authService.getUser();
      if (!currentUser) {
        this.errorMessage = 'User session not found. Please log in.';
        this.loading = false;
        return;
      }

      this.profile.auth_id = currentUser.id;
      
      const metadata = currentUser.user_metadata || {};
      const fallbackName = metadata['full_name'] || currentUser.email?.split('@')[0] || 'New User';
      this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;

      // Query profiles table
      const { data, error } = await this.authService.supabaseClient
        .from('profiles')
        .select('*')
        .eq('auth_id', currentUser.id)
        .maybeSingle();

      if (error) {
        throw error;
      }

      if (data) {
        this.profile = {
          id: data.id,
          auth_id: data.auth_id,
          full_name: data.full_name || '',
          social_media_url: data.social_media_url || [],
          resume_url: data.resume_url || '',
          interest_area: data.interest_area || [],
          first_time_login: data.first_time_login ?? true
        };
      } else {
        // Fallback to Google user metadata
        const metadata = currentUser.user_metadata || {};
        const fallbackName = metadata['full_name'] || currentUser.email?.split('@')[0] || 'New User';
        this.profile.full_name = fallbackName;
        this.profile.social_media_url = [];
        this.profile.interest_area = ['Full-Stack', 'Web Development'];
        this.profile.first_time_login = true;
      }
    } catch (err: any) {
      console.error('Error fetching profile:', err);
      this.errorMessage = err.message || 'Failed to load profile.';
    } finally {
      this.loading = false;
      this.cdr.detectChanges();
    }
  }

  toggleEditMode() {
    this.isEditMode = true;
    this.backupProfile = JSON.parse(JSON.stringify(this.profile));
    this.successMessage = '';
    this.errorMessage = '';
  }

  cancelEdit() {
    if (this.backupProfile) {
      this.profile = JSON.parse(JSON.stringify(this.backupProfile));
    }
    this.isEditMode = false;
    this.newInterest = '';
    this.newSocialUrl = '';
  }

  async saveProfile() {
    if (!this.profile.full_name?.trim()) {
      this.errorMessage = 'Full Name is required.';
      return;
    }

    this.saving = true;
    this.successMessage = '';
    this.errorMessage = '';

    try {
      const payload = {
        auth_id: this.profile.auth_id,
        full_name: this.profile.full_name.trim(),
        social_media_url: this.profile.social_media_url,
        resume_url: this.profile.resume_url?.trim() || null,
        interest_area: this.profile.interest_area,
        first_time_login: false
      };

      let response;
      if (this.profile.id) {
        response = await this.authService.supabaseClient
          .from('profiles')
          .update(payload)
          .eq('id', this.profile.id)
          .select()
          .single();
      } else {
        response = await this.authService.supabaseClient
          .from('profiles')
          .insert(payload)
          .select()
          .single();
      }

      if (response.error) {
        throw response.error;
      }

      if (response.data) {
        this.profile = {
          id: response.data.id,
          auth_id: response.data.auth_id,
          full_name: response.data.full_name || '',
          social_media_url: response.data.social_media_url || [],
          resume_url: response.data.resume_url || '',
          interest_area: response.data.interest_area || [],
          first_time_login: response.data.first_time_login ?? false
        };
        this.successMessage = 'Profile saved successfully!';
        this.isEditMode = false;
        this.cdr.detectChanges();
        
        // Hide success message after 3 seconds
        setTimeout(() => {
          this.successMessage = '';
          this.cdr.detectChanges();
        }, 3000);
      }
    } catch (err: any) {
      console.error('Error saving profile:', err);
      this.errorMessage = err.message || 'Failed to save profile.';
      this.cdr.detectChanges();
    } finally {
      this.saving = false;
      this.cdr.detectChanges();
    }
  }

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

  addSocialUrl(event?: Event) {
    if (event) {
      event.preventDefault();
    }
    const url = this.newSocialUrl.trim();
    if (url) {
      // Simple validation for URL format
      try {
        new URL(url.startsWith('http') ? url : 'https://' + url);
        if (!this.profile.social_media_url.includes(url)) {
          this.profile.social_media_url.push(url);
        }
        this.newSocialUrl = '';
      } catch (e) {
        this.errorMessage = 'Please enter a valid URL.';
        setTimeout(() => {
          this.errorMessage = '';
        }, 3000);
      }
    }
  }

  removeSocialUrl(index: number) {
    this.profile.social_media_url.splice(index, 1);
  }

  async onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    const fileExt = file.name.split('.').pop()?.toLowerCase();

    if (fileExt !== 'pdf') {
      this.errorMessage = 'Only PDF files are allowed.';
      input.value = '';
      this.cdr.detectChanges();
      return;
    }

    this.uploadingResume = true;
    this.errorMessage = '';
    this.cdr.detectChanges();

    try {
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
      console.error('Error uploading resume in profile:', err);
      this.errorMessage = err.message || 'Failed to upload resume.';
      this.profile.resume_url = '';
    } finally {
      this.uploadingResume = false;
      this.cdr.detectChanges();
    }
  }

  removeResume() {
    this.profile.resume_url = '';
    this.cdr.detectChanges();
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
}
