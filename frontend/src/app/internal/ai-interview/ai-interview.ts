import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
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
  cdr = inject(ChangeDetectorRef);

  googleAvatarUrl = '';

  async ngOnInit() {
    try {
      const user = await this.authService.getUser();
      if (user) {
        const metadata = user.user_metadata || {};
        const fallbackName = metadata['full_name'] || user.email?.split('@')[0] || 'User';
        this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;
      }
    } catch (err) {
      console.error('Error fetching user metadata in ai-interview:', err);
    } finally {
      this.cdr.detectChanges();
    }
  }
}
