import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { InterviewService } from '../../services/interview.service';

@Component({
  selector: 'app-employer-reports',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './employer-reports.html',
  styleUrl: './employer-reports.css',
})
export class EmployerReports implements OnInit {
  interviewService = inject(InterviewService);

  reports: any[] = [];
  isLoading = true;
  errorMessage = '';

  async ngOnInit() {
    try {
      this.reports = await this.interviewService.listReports();
    } catch (e: any) {
      this.errorMessage = 'Failed to load reports: ' + (e.error?.detail || e.message);
    } finally {
      this.isLoading = false;
    }
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString();
  }
}
