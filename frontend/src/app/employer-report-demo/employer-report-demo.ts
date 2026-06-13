import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-employer-report-demo',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './employer-report-demo.html',
  styleUrls: ['./employer-report-demo.css']
})
export class EmployerReportDemo implements OnInit {
  report: any = null;
  loading: boolean = true;
  error: string | null = null;

  ngOnInit() {
    this.fetchReport();
  }

  async fetchReport() {
    try {
      this.loading = true;
      this.error = null;
      
      const apiBase = environment.backendUrl || '/_/backend';
      const res = await fetch(`${apiBase}/api/v1/interview-report/demo`);
      
      if (!res.ok) {
        throw new Error('Failed to fetch report');
      }
      this.report = await res.json();
    } catch (err: any) {
      this.error = err.message || 'An error occurred';
    } finally {
      this.loading = false;
    }
  }

  printReport() {
    window.print();
  }
}
