import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { InterviewService } from '../../services/interview.service';

@Component({
  selector: 'app-employer-report',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './employer-report.html',
  styleUrl: './employer-report.css',
})
export class EmployerReport implements OnInit {
  route = inject(ActivatedRoute);
  interviewService = inject(InterviewService);

  reportId = '';
  report: any = null;
  reportJson: any = null;
  isLoading = true;
  errorMessage = '';

  async ngOnInit() {
    this.reportId = this.route.snapshot.paramMap.get('reportId') || '';
    if (!this.reportId) {
      this.errorMessage = 'Report ID is missing.';
      this.isLoading = false;
      return;
    }

    try {
      this.report = await this.interviewService.getReport(this.reportId);
      this.reportJson = this.report.report_json;
    } catch (e: any) {
      this.errorMessage = 'Failed to load report: ' + (e.error?.detail || e.message);
    } finally {
      this.isLoading = false;
    }
  }

  printReport() {
    window.print();
  }
}
