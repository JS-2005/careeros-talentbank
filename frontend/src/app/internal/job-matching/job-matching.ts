import { Component, ChangeDetectorRef, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';
import { environment } from '../../../environments/environment';

export interface Job {
  job_id: string;
  title: string;
  company_name: string;
  location: string;
  salary?: string;
  salary_parsed?: {
    currency: string;
    min_salary: number;
    max_salary?: number;
    pay_period: string;
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
          job.title.toLowerCase().includes(this.topbarSearchQuery) ||
          job.company_name.toLowerCase().includes(this.topbarSearchQuery) ||
          job.location.toLowerCase().includes(this.topbarSearchQuery) ||
          job.description.toLowerCase().includes(this.topbarSearchQuery)
        )
      };
    }).filter(group => group.jobs.length > 0);

    // Filter remapResults
    this.filteredRemapResults = this.remapResults.filter(job => 
      job.title.toLowerCase().includes(this.topbarSearchQuery) ||
      job.company_name.toLowerCase().includes(this.topbarSearchQuery) ||
      job.location.toLowerCase().includes(this.topbarSearchQuery) ||
      job.description.toLowerCase().includes(this.topbarSearchQuery) ||
      job.remap_description?.toLowerCase().includes(this.topbarSearchQuery)
    );

    this.cdr.detectChanges();
  }

  countries = [
    'United States', 'Canada', 'United Kingdom', 'Australia', 'Germany',
    'France', 'India', 'China', 'Japan', 'Singapore', 'Malaysia',
    'Brazil', 'Mexico', 'South Africa'
  ];

  // Raw mock database before AI processing
  private mockRawJobs: Job[] = [
    {
      job_id: 'job_001',
      title: 'Software Engineer Intern',
      company_name: 'TechCorp Solutions',
      location: 'Kuala Lumpur, Malaysia',
      salary: 'RM 3,000',
      salary_parsed: { currency: 'RM', min_salary: 3000, pay_period: 'month' },
      schedule_type: 'Full-time',
      work_from_home: true,
      description: 'We are looking for a passionate Software Engineer Intern to join our web team. You will work on building clean, high-performance user interfaces using Angular and TypeScript.',
      key_responsibilities: [
        'Collaborate with senior developers to design and implement new UI features.',
        'Write robust, testable, and clean code.',
        'Participate in code reviews and agile ceremonies.'
      ],
      core_skills: ['Angular', 'TypeScript', 'HTML5', 'CSS3'],
      soft_skills: ['Teamwork', 'Communication', 'Problem Solving']
    },
    {
      job_id: 'job_002',
      title: 'Frontend Developer',
      company_name: 'WebStudio Asia',
      location: 'Selangor, Malaysia',
      salary: 'RM 5,500',
      salary_parsed: { currency: 'RM', min_salary: 5500, pay_period: 'month' },
      schedule_type: 'Full-time',
      work_from_home: false,
      description: 'Join our creative studio as a Frontend Developer. You will turn beautiful Figma designs into interactive, high-quality web applications.',
      key_responsibilities: [
        'Translate Figma design mockups into pixel-perfect web pages.',
        'Collaborate with UX/UI designers to improve user experience.',
        'Ensure cross-browser compatibility and mobile responsiveness.'
      ],
      core_skills: ['JavaScript', 'HTML', 'CSS', 'Sass'],
      soft_skills: ['Creative Thinking', 'Adaptability']
    },
    {
      job_id: 'job_003',
      title: 'Data Analyst Intern',
      company_name: 'FinanceFlow Systems',
      location: 'Singapore',
      salary: 'S$ 1,500',
      salary_parsed: { currency: 'S$', min_salary: 1500, pay_period: 'month' },
      schedule_type: 'Internship',
      work_from_home: false,
      description: 'Looking for a Data Analyst Intern to help audit our financial data, preprocess raw transactions, and create analytics dashboards.',
      key_responsibilities: [
        'Collect and clean raw data from financial records.',
        'Build automated dashboards for quarterly reports.'
      ],
      core_skills: ['Data Cleaning', 'Excel', 'Data Visualization'],
      soft_skills: ['Analytical Mindset', 'Attention to Detail']
    },
    {
      job_id: 'job_004',
      title: 'Full Stack Engineer',
      company_name: 'DevGroup Australia',
      location: 'Sydney, Australia',
      salary: 'A$ 85,000',
      salary_parsed: { currency: 'A$', min_salary: 85000, pay_period: 'year' },
      schedule_type: 'Full-time',
      work_from_home: true,
      description: 'DevGroup is hiring a Full Stack Developer to help build our cloud SaaS platforms, design schemas, and build backend APIs.',
      key_responsibilities: [
        'Develop robust server-side APIs.',
        'Connect backend services with premium Angular dashboards.',
        'Design database schemas and optimize query speeds.'
      ],
      core_skills: ['TypeScript', 'Node.js', 'Express', 'Angular'],
      soft_skills: ['Self-management', 'Critical thinking']
    }
  ];

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
    this.topbarSearchQuery = '';
    this.filterJobs();
    this.cdr.detectChanges();
  }

  async onSubmit() {
    if (!this.country) {
      alert('Please select a country.');
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

      // Setup initial raw jobs as extracting in groups
      this.isEnhancing = true;
      const groupsMap = new Map<string, Job[]>();
      for (const j of rawJobs) {
        const role = j.target_job_role || 'General';
        if (!groupsMap.has(role)) {
          groupsMap.set(role, []);
        }
        groupsMap.get(role)!.push({ ...j, isExtracting: true });
      }
      this.extractedJobsGroups = Array.from(groupsMap.entries()).map(([role, jobs]) => ({ role, jobs }));
      this.filterJobs();
      this.cdr.detectChanges();

      // 4. Concurrently run Gemma extract-single-job for each job, updating their UI status as they finish
      const extractedJobs: Job[] = [];
      
      const extractionPromises = rawJobs.map(async (job) => {
        try {
          const extractRes = await fetch(`${environment.backendUrl}/api/v1/extract-single-job`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ raw_job: job })
          });

          if (!extractRes.ok) {
            throw new Error('Extraction failed');
          }

          const extractedJob = await extractRes.json();
          extractedJob.isExtracting = false;
          extractedJob.extractionFailed = false;

          // Update UI card extraction status
          this.updateJobInGroups(extractedJob);
          extractedJobs.push(extractedJob);
        } catch (err) {
          console.error(`Failed to extract job ${job.job_id}:`, err);
          const failedJob = { ...job, isExtracting: false, extractionFailed: true };
          this.updateJobInGroups(failedJob);
          extractedJobs.push(failedJob);
        }
        this.cdr.detectChanges();
      });

      // Wait for all extractions to finish
      await Promise.all(extractionPromises);
      this.isEnhancing = false;
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
          user_data_dict: userDataDict,
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
