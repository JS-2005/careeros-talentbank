import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { AuthService } from './auth-service';
import { firstValueFrom } from 'rxjs';

export interface AnswerItem {
  question: string;
  answer_text: string;
  answer_order: number;
}

@Injectable({
  providedIn: 'root'
})
export class InterviewService {
  private baseUrl = environment.backendUrl || '/_/backend';

  constructor(private http: HttpClient, private authService: AuthService) {}

  private async getHeaders(): Promise<HttpHeaders> {
    const { data: { session } } = await this.authService.supabaseClient.auth.getSession();
    const token = session?.access_token || '';
    return new HttpHeaders({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    });
  }

  async createInterviewSession(target_job_title: string, target_job_id?: string, target_company_name?: string): Promise<{ session_id: string }> {
    const headers = await this.getHeaders();
    const payload = { target_job_title, target_job_id, target_company_name };
    return firstValueFrom(this.http.post<{ session_id: string }>(`${this.baseUrl}/api/v1/interview-session/create`, payload, { headers }));
  }

  async submitAnswers(session_id: string, consent_given: boolean, answers: AnswerItem[]): Promise<{ status: string }> {
    const headers = await this.getHeaders();
    const payload = { consent_given, answers };
    return firstValueFrom(this.http.post<{ status: string }>(`${this.baseUrl}/api/v1/interview-session/${session_id}/submit`, payload, { headers }));
  }

  async generateReport(session_id: string): Promise<{ report_id: string, status: string }> {
    const headers = await this.getHeaders();
    const payload = { session_id };
    return firstValueFrom(this.http.post<{ report_id: string, status: string }>(`${this.baseUrl}/api/v1/interview-report/generate`, payload, { headers }));
  }

  async getReport(reportId: string): Promise<any> {
    const headers = await this.getHeaders();
    return firstValueFrom(this.http.get<any>(`${this.baseUrl}/api/v1/interview-report/${reportId}`, { headers }));
  }

  async listReports(): Promise<any[]> {
    const headers = await this.getHeaders();
    return firstValueFrom(this.http.get<any[]>(`${this.baseUrl}/api/v1/interview-reports`, { headers }));
  }
}
