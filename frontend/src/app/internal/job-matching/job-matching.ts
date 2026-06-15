import { Component, ChangeDetectorRef, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';
import { environment } from '../../../environments/environment';

export interface Job {
  job_id: string;
  target_job_role?: string;
  title: string;
  company_name: string;
  location: string;
  salary?: string;
  salary_parsed?: {
    currency?: string | null;
    min_salary: number;
    max_salary?: number;
    pay_period?: string | null;
  };
  schedule_type?: string;
  work_from_home?: boolean;
  description: string;
  key_responsibilities: string[];
  core_skills: string[];
  soft_skills: string[];
  logical_match_score?: number;
  remap_description?: string;
  unmatched_mandatory_skills?: string[];
  unmatched_responsibilities?: string[];
  matched_optional_skills?: string[];
  source_link?: string;
  posted_at?: string;
  matching_method?: string;
  isExtracting?: boolean;
  extractionFailed?: boolean;
}

@Component({
  selector: 'app-job-matching',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './job-matching.html',
  styleUrl: './job-matching.css',
})
export class JobMatching implements OnInit {
  private cdr = inject(ChangeDetectorRef);
  internal = inject(Internal);
  authService = inject(AuthService);

  googleAvatarUrl = '';
  userFullName = 'User';
  profileResumeUrl = '';

  async ngOnInit() {
    try {
      const user = await this.authService.getUser();
      if (user) {
        const metadata = user.user_metadata || {};
        const fallbackName = metadata['full_name'] || user.email?.split('@')[0] || 'User';
        this.userFullName = fallbackName;
        this.googleAvatarUrl = metadata['avatar_url'] || metadata['picture'] || `https://ui-avatars.com/api/?name=${encodeURIComponent(fallbackName)}&background=0D8ABC&color=fff&size=100`;

        // Fetch profile resume url
        const { data: profileData, error: profileError } = await this.authService.supabaseClient
          .from('profiles')
          .select('resume_url')
          .eq('auth_id', user.id)
          .maybeSingle();

        if (profileError) throw profileError;

        if (profileData && profileData.resume_url) {
          this.profileResumeUrl = profileData.resume_url;
        }

        // Fetch saved jobs from backend
        try {
          const sessionRes = await this.authService.supabaseClient.auth.getSession();
          const token = sessionRes.data.session?.access_token;
          if (token) {
            const savedRes = await fetch(`${environment.backendUrl}/api/v1/get-saved-jobs`, {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            });
            if (savedRes.ok) {
              const savedData = await savedRes.json();
              if (savedData.job_data && savedData.job_data.length > 0) {
                const groupsMap = new Map<string, Job[]>();
                for (const job of savedData.job_data) {
                  const role = job.target_job_role || 'General';
                  if (!groupsMap.has(role)) {
                    groupsMap.set(role, []);
                  }
                  groupsMap.get(role)!.push({ ...job, isExtracting: false });
                }
                this.extractedJobsGroups = Array.from(groupsMap.entries()).map(([role, jobs]) => ({ role, jobs }));
                this.hasSearched = true;
              }
              if (savedData.final_job_data && savedData.final_job_data.length > 0) {
                this.remapResults = savedData.final_job_data.map((job: any) => ({ ...job, isExtracting: false }));
                this.remapResults.sort((a, b) => (b.logical_match_score || 0) - (a.logical_match_score || 0));
                this.currentTab = 'recommendations';
              }
            }
          }
        } catch (err) {
          console.warn('Could not retrieve saved jobs:', err);
        }
      }
    } catch (err) {
      console.error('Error fetching user metadata in job-matching:', err);
    } finally {
      this.filterJobs();
      this.cdr.detectChanges();
    }
  }

  // Search filter states
  country = 'Malaysia';
  state = '';
  manualSearchQuery = '';
  expectedSalary = 0;
  isIntern = false;

  showAdvancedFilters = false;
  currentTab: 'search' | 'recommendations' = 'search';

  // Loading/Progress states
  isLoading = false;      // SerpApi Job Search phase
  isEnhancing = false;    // Gemma detail extraction phase
  isScoring = false;      // ReMAP match scoring phase

  // Results state
  hasSearched = false;
  extractedJobsGroups: { role: string; jobs: Job[] }[] = [];
  remapResults: Job[] = [];
  selectedJob: Job | null = null;

  // Topbar Search filter states
  topbarSearchQuery = '';
  filteredExtractedJobsGroups: { role: string; jobs: Job[] }[] = [];
  filteredRemapResults: Job[] = [];

  onTopbarSearch(event: Event) {
    const query = (event.target as HTMLInputElement).value.toLowerCase();
    this.topbarSearchQuery = query;
    this.filterJobs();
  }

  filterJobs() {
    if (!this.topbarSearchQuery) {
      this.filteredExtractedJobsGroups = this.extractedJobsGroups;
      this.filteredRemapResults = this.remapResults;
      this.cdr.detectChanges();
      return;
    }

    // Filter extractedJobsGroups
    this.filteredExtractedJobsGroups = this.extractedJobsGroups.map(group => {
      return {
        role: group.role,
        jobs: group.jobs.filter(job => 
          (job.title || '').toLowerCase().includes(this.topbarSearchQuery) ||
          (job.company_name || '').toLowerCase().includes(this.topbarSearchQuery) ||
          (job.location || '').toLowerCase().includes(this.topbarSearchQuery) ||
          (job.description || '').toLowerCase().includes(this.topbarSearchQuery)
        )
      };
    }).filter(group => group.jobs.length > 0);

    // Filter remapResults
    this.filteredRemapResults = this.remapResults.filter(job => 
      (job.title || '').toLowerCase().includes(this.topbarSearchQuery) ||
      (job.company_name || '').toLowerCase().includes(this.topbarSearchQuery) ||
      (job.location || '').toLowerCase().includes(this.topbarSearchQuery) ||
      (job.description || '').toLowerCase().includes(this.topbarSearchQuery) ||
      (job.remap_description || '').toLowerCase().includes(this.topbarSearchQuery)
    );

    this.cdr.detectChanges();
  }

  countries = [
    'United States', 'Canada', 'United Kingdom', 'Australia', 'Germany',
    'France', 'India', 'China', 'Japan', 'Singapore', 'Malaysia',
    'Brazil', 'Mexico', 'South Africa'
  ];

  // Production note: job matching uses only live SerpAPI/backend data.


  get currencySymbol(): string {
    const currencyMap: { [key: string]: string } = {
      'United States': '$', 'Canada': 'CA$', 'United Kingdom': '£',
      'Australia': 'A$', 'Germany': '€', 'France': '€', 'India': '₹',
      'China': '¥', 'Japan': '¥', 'Singapore': 'S$', 'Malaysia': 'RM',
      'Brazil': 'R$', 'Mexico': 'Mex$', 'South Africa': 'R'
    };
    return currencyMap[this.country] || '$';
  }

  toggleAdvancedFilters() {
    this.showAdvancedFilters = !this.showAdvancedFilters;
  }


  switchTab(tab: 'search' | 'recommendations') {
    this.currentTab = tab;
  }

  openJobDetail(job: Job) {
    this.selectedJob = job;
  }

  closeJobDetail() {
    this.selectedJob = null;
  }

  resetSearch() {
    this.hasSearched = false;
    this.extractedJobsGroups = [];
    this.remapResults = [];
    this.currentTab = 'search';
    this.expectedSalary = 0;
    this.state = '';
    this.manualSearchQuery = '';
    this.topbarSearchQuery = '';
    this.filterJobs();
    this.cdr.detectChanges();
  }

  async onSubmit() {
    if (!this.country) {
      alert('Please select a country.');
      return;
    }

    if (!this.profileResumeUrl && !this.manualSearchQuery.trim()) {
      alert('Please upload a resume in your profile or enter a target role / keyword.');
      return;
    }

    this.hasSearched = true;
    this.isLoading = true;
    this.isEnhancing = false;
    this.isScoring = false;
    this.extractedJobsGroups = [];
    this.remapResults = [];
    this.currentTab = 'search';
    this.filterJobs();
    this.cdr.detectChanges();

    try {
      // 1. Download user's resume PDF from Supabase if profileResumeUrl exists
      let file: File | null = null;
      if (this.profileResumeUrl) {
        try {
          const downloadRes = await fetch(this.profileResumeUrl);
          if (downloadRes.ok) {
            const blob = await downloadRes.blob();
            file = new File([blob], 'resume.pdf', { type: 'application/pdf' });
          } else {
            console.error('Failed to download resume from url:', this.profileResumeUrl);
          }
        } catch (err) {
          console.error('Error fetching resume file blob:', err);
        }
      }

      // 2. Fetch User Token
      const sessionRes = await this.authService.supabaseClient.auth.getSession();
      const token = sessionRes.data.session?.access_token;
      if (!token) {
        alert('You must be signed in to perform job matching.');
        this.isLoading = false;
        this.cdr.detectChanges();
        return;
      }

      // 3. Trigger Search Initial Jobs
      const formData = new FormData();
      formData.append('country', this.country);
      if (this.state) formData.append('state', this.state);
      formData.append('is_intern', String(this.isIntern));
      if (this.expectedSalary > 0) formData.append('expected_salary', String(this.expectedSalary));
      if (this.manualSearchQuery.trim()) formData.append('search_query', this.manualSearchQuery.trim());
      if (file) formData.append('file', file);

      const searchRes = await fetch(`${environment.backendUrl}/api/v1/search-initial-jobs`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!searchRes.ok) {
        const errorData = await searchRes.json();
        throw new Error(errorData?.detail || 'Job search request failed');
      }

      const searchResult = await searchRes.json();
      const rawJobs: any[] = searchResult.raw_job_result || [];
      const userDataDict = searchResult.user_data_dict;

      this.isLoading = false;

      if (rawJobs.length === 0) {
        alert('No jobs found for the specified query and filters.');
        this.hasSearched = false;
        this.cdr.detectChanges();
        return;
      }

      // 4. Backend now returns SerpAPI results already structured by the fast parser.
      // This removes the old one-request-per-job Gemma extraction bottleneck.
      this.isEnhancing = false;
      const extractedJobs: Job[] = rawJobs.map((job: any) => ({
        ...job,
        isExtracting: false,
        extractionFailed: false,
        key_responsibilities: job.key_responsibilities || [],
        core_skills: job.core_skills || [],
        soft_skills: job.soft_skills || []
      }));

      const groupsMap = new Map<string, Job[]>();
      for (const j of extractedJobs) {
        const role = j.target_job_role || 'General';
        if (!groupsMap.has(role)) {
          groupsMap.set(role, []);
        }
        groupsMap.get(role)!.push(j);
      }
      this.extractedJobsGroups = Array.from(groupsMap.entries()).map(([role, jobs]) => ({ role, jobs }));
      this.filterJobs();
      this.cdr.detectChanges();

      if (!userDataDict || Object.keys(userDataDict).length === 0) {
        this.currentTab = 'search';
        this.filterJobs();
        this.cdr.detectChanges();
        return;
      }

      this.isScoring = true;
      this.cdr.detectChanges();

      // 5. Trigger ReMAP sorting & Scoring
      const remapRes = await fetch(`${environment.backendUrl}/api/v1/remap-and-sort-jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          user_data_dict: userDataDict || {},
          organised_job_result: extractedJobs
        })
      });

      if (!remapRes.ok) {
        const errorData = await remapRes.json();
        throw new Error(errorData?.detail || 'ReMAP scoring failed');
      }

      const remapResultData = await remapRes.json();
      this.remapResults = remapResultData.jobs || [];

      // Sort by match score descending
      this.remapResults.sort((a, b) => (b.logical_match_score || 0) - (a.logical_match_score || 0));

      this.isScoring = false;
      this.currentTab = 'recommendations';
      this.filterJobs();
      this.cdr.detectChanges();

    } catch (err: any) {
      console.error('Error during job matching process:', err);
      alert('An error occurred during job matching: ' + err.message);
      this.isLoading = false;
      this.isEnhancing = false;
      this.isScoring = false;
      this.cdr.detectChanges();
    }
  }

  private updateJobInGroups(updatedJob: Job) {
    for (const group of this.extractedJobsGroups) {
      const idx = group.jobs.findIndex(j => j.job_id === updatedJob.job_id);
      if (idx !== -1) {
        group.jobs[idx] = updatedJob;
        break;
      }
    }
    this.filterJobs();
  }
}
