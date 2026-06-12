import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';

@Component({
  selector: 'app-marketplace',
  imports: [],
  templateUrl: './marketplace.html',
  styleUrl: './marketplace.css',
})
export class Marketplace implements OnInit {
  internal = inject(Internal);
  authService = inject(AuthService);
  cdr = inject(ChangeDetectorRef);

  googleAvatarUrl = '';
  userFullName = 'User';
  activeModal: 'normal' | 'event' | 'recruitment' | null = null;
  selectedMediaFile: File | null = null;
  isSubmitting = false;

  searchQuery = '';
  feedItems: any[] = [];
  allFeedItems: any[] = [];
  eventItems: any[] = [];

  async ngOnInit() {
    try {
      const user = await this.authService.getUser();
      if (user) {
        const metadata = user.user_metadata || {};
        const fallbackName = metadata['full_name'] || user.email?.split('@')[0] || 'User';
        this.userFullName = fallbackName;
        this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;
      }
      await this.loadPosts();
    } catch (err) {
      console.error('Error fetching user metadata in marketplace:', err);
    } finally {
      this.cdr.detectChanges();
    }
  }

  async loadPosts() {
    try {
      // 1. Fetch posts and their subclasses
      const { data: postsData, error: postsError } = await this.authService.supabaseClient
        .from('posts')
        .select(`
          id,
          created_at,
          auth_id,
          post_type,
          media_url,
          normal_posts(content),
          event_posts(title, datetime, location, virtual_link, description),
          recruitment_posts(title, work_mode, compensation, skills, job_application_url, job_description, urgent)
        `)
        .eq('is_deleted', false)
        .order('created_at', { ascending: false });

      if (postsError) throw postsError;

      // 2. Fetch profiles to map names and avatars
      const { data: profilesData, error: profilesError } = await this.authService.supabaseClient
        .from('profiles')
        .select('auth_id, full_name');

      if (profilesError) throw profilesError;

      const profileMap = new Map<string, string>();
      if (profilesData) {
        profilesData.forEach(p => {
          if (p.auth_id) {
            profileMap.set(p.auth_id, p.full_name || 'User');
          }
        });
      }

      // 3. Map database posts to feedItems and eventItems
      const mappedFeedItems: any[] = [];
      const mappedEventItems: any[] = [];

      if (postsData) {
        postsData.forEach((post: any) => {
          const authorName = profileMap.get(post.auth_id) || 'User';
          const timeFormatted = this.formatRelativeTime(post.created_at);

          if (post.post_type === 'normal') {
            const normal = Array.isArray(post.normal_posts) ? post.normal_posts[0] : post.normal_posts;
            const content = normal?.content || '';
            mappedFeedItems.push({
              id: post.id,
              type: 'post',
              user: authorName,
              userRole: 'Community Member',
              text: content,
              likes: 0,
              comments: 0,
              mediaUrl: post.media_url,
              created_at: post.created_at
            });
          } else if (post.post_type === 'recruitment') {
            const recruit = Array.isArray(post.recruitment_posts) ? post.recruitment_posts[0] : post.recruitment_posts;
            const title = recruit?.title || 'Job Title';
            const desc = recruit?.job_description || '';
            const skills = recruit?.skills || [];
            const comp = recruit?.compensation || '';
            const url = recruit?.job_application_url || '#';
            const urgent = recruit?.urgent || false;
            
            mappedFeedItems.push({
              id: post.id,
              type: 'job',
              company: authorName,
              companyLogo: authorName.charAt(0).toUpperCase() || 'C',
              postedTime: timeFormatted,
              urgent: urgent,
              title: title,
              desc: desc,
              tags: skills,
              compensation: comp,
              url: url,
              mediaUrl: post.media_url,
              created_at: post.created_at
            });
          } else if (post.post_type === 'event') {
            const event = Array.isArray(post.event_posts) ? post.event_posts[0] : post.event_posts;
            const title = event?.title || 'Event Title';
            const dateStr = event?.datetime;
            const location = event?.location || '';
            const virtualLink = event?.virtual_link || '';
            const desc = event?.description || '';

            // Format date nicely
            let formattedDate = '';
            if (dateStr) {
              const d = new Date(dateStr);
              formattedDate = d.toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              });
            }

            mappedFeedItems.push({
              id: post.id,
              type: 'event',
              user: authorName,
              userRole: 'Event Organizer',
              postedTime: timeFormatted,
              title: title,
              desc: desc,
              eventDate: formattedDate,
              location: location,
              virtualLink: virtualLink,
              mediaUrl: post.media_url,
              created_at: post.created_at
            });
          }
        });
      }

      // Sort feed items by created_at descending
      this.allFeedItems = mappedFeedItems.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      this.filterFeed();
      this.eventItems = [];
    } catch (err) {
      console.error('Error loading posts:', err);
    } finally {
      this.cdr.detectChanges();
    }
  }

  onSearch(event: Event) {
    const query = (event.target as HTMLInputElement).value.toLowerCase();
    this.searchQuery = query;
    this.filterFeed();
  }

  filterFeed() {
    if (!this.searchQuery) {
      this.feedItems = this.allFeedItems;
      this.cdr.detectChanges();
      return;
    }

    this.feedItems = this.allFeedItems.filter(item => {
      if (item.type === 'post') {
        const matchesUser = item.user?.toLowerCase().includes(this.searchQuery);
        const matchesText = item.text?.toLowerCase().includes(this.searchQuery);
        return matchesUser || matchesText;
      } else if (item.type === 'job') {
        const matchesTitle = item.title?.toLowerCase().includes(this.searchQuery);
        const matchesDesc = item.desc?.toLowerCase().includes(this.searchQuery);
        const matchesCompany = item.company?.toLowerCase().includes(this.searchQuery);
        const matchesTags = item.tags?.some((tag: string) => tag.toLowerCase().includes(this.searchQuery));
        return matchesTitle || matchesDesc || matchesCompany || matchesTags;
      } else if (item.type === 'event') {
        const matchesTitle = item.title?.toLowerCase().includes(this.searchQuery);
        const matchesDesc = item.desc?.toLowerCase().includes(this.searchQuery);
        const matchesLocation = item.location?.toLowerCase().includes(this.searchQuery);
        const matchesOrganizer = item.user?.toLowerCase().includes(this.searchQuery);
        return matchesTitle || matchesDesc || matchesLocation || matchesOrganizer;
      }
      return false;
    });

    this.cdr.detectChanges();
  }

  formatRelativeTime(dateStr: string): string {
    const now = new Date();
    const past = new Date(dateStr);
    const diffMs = now.getTime() - past.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  }

  openModal(type: 'normal' | 'event' | 'recruitment') {
    this.activeModal = type;
  }

  closeModal() {
    this.activeModal = null;
    this.clearSelectedMedia();
    this.cdr.detectChanges();
  }

  triggerMediaUpload() {
    const fileInput = document.getElementById('post-media-input') as HTMLInputElement;
    if (fileInput) fileInput.click();
  }

  onMediaSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedMediaFile = input.files[0];
    }
  }

  clearSelectedMedia() {
    this.selectedMediaFile = null;
    const fileInput = document.getElementById('post-media-input') as HTMLInputElement;
    if (fileInput) fileInput.value = '';
  }

  async submitPost(event: Event) {
    event.preventDefault();
    if (this.isSubmitting) return;

    try {
      this.isSubmitting = true;
      const user = await this.authService.getUser();
      if (!user) {
        alert('You must be signed in to create a post.');
        return;
      }

      const form = event.target as HTMLFormElement;

      // 1. Insert into public.posts
      const { data: postData, error: postError } = await this.authService.supabaseClient
        .from('posts')
        .insert({
          post_type: this.activeModal === 'normal' ? 'normal' : (this.activeModal === 'event' ? 'event' : 'recruitment'),
          auth_id: user.id
        })
        .select()
        .single();

      if (postError) throw postError;

      let uploadedMediaUrl = '';

      // 2. Upload media file to posts-bucket if selected
      if (this.selectedMediaFile) {
        const fileExt = this.selectedMediaFile.name.split('.').pop();
        const fileName = `${Date.now()}.${fileExt}`;
        const filePath = `${user.id}/${postData.id}/${fileName}`;

        const { error: uploadError } = await this.authService.supabaseClient
          .storage
          .from('posts-bucket')
          .upload(filePath, this.selectedMediaFile);

        if (uploadError) throw uploadError;

        const { data: publicUrlData } = this.authService.supabaseClient
          .storage
          .from('posts-bucket')
          .getPublicUrl(filePath);

        uploadedMediaUrl = publicUrlData.publicUrl;

        // Update posts table with media_url
        const { error: updatePostError } = await this.authService.supabaseClient
          .from('posts')
          .update({ media_url: uploadedMediaUrl })
          .eq('id', postData.id);

        if (updatePostError) throw updatePostError;
      }

      // 3. Insert subclass details
      if (this.activeModal === 'normal') {
        const textarea = form.querySelector('#post-text') as HTMLTextAreaElement;
        const { error: subclassError } = await this.authService.supabaseClient
          .from('normal_posts')
          .insert({
            id: postData.id,
            content: textarea.value
          });

        if (subclassError) throw subclassError;

      } else if (this.activeModal === 'event') {
        const title = (form.querySelector('#event-title') as HTMLInputElement).value;
        const dateVal = (form.querySelector('#event-date') as HTMLInputElement).value;
        const timeVal = (form.querySelector('#event-time') as HTMLInputElement).value;
        const location = (form.querySelector('#event-location') as HTMLInputElement).value;
        const desc = (form.querySelector('#event-desc') as HTMLTextAreaElement).value;

        // Combine date and time
        const combinedDateTime = new Date(`${dateVal}T${timeVal}`).toISOString();

        const { error: subclassError } = await this.authService.supabaseClient
          .from('event_posts')
          .insert({
            id: postData.id,
            title: title,
            datetime: combinedDateTime,
            location: location,
            virtual_link: location.toLowerCase().startsWith('http') ? location : null,
            description: desc
          });

        if (subclassError) throw subclassError;

      } else if (this.activeModal === 'recruitment') {
        const title = (form.querySelector('#job-title') as HTMLInputElement).value;
        const workMode = (form.querySelector('#job-location') as HTMLSelectElement).value;
        const comp = (form.querySelector('#job-comp') as HTMLInputElement).value;
        const desc = (form.querySelector('#job-desc') as HTMLTextAreaElement).value;
        const tagsInput = (form.querySelector('#job-tags') as HTMLInputElement).value;
        const urgent = (form.querySelector('#job-urgent') as HTMLInputElement).checked;
        const jobUrl = (form.querySelector('#job-url') as HTMLInputElement).value;

        const skills = tagsInput.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);

        const { error: subclassError } = await this.authService.supabaseClient
          .from('recruitment_posts')
          .insert({
            id: postData.id,
            title: title,
            work_mode: workMode,
            compensation: comp,
            skills: skills,
            job_application_url: jobUrl,
            job_description: desc,
            urgent: urgent
          });

        if (subclassError) throw subclassError;
      }

      this.closeModal();
      this.loadPosts();

    } catch (err) {
      console.error('Error submitting post:', err);
      alert('Failed to submit post: ' + (err as any).message);
    } finally {
      this.isSubmitting = false;
      this.cdr.detectChanges();
    }
  }
}
