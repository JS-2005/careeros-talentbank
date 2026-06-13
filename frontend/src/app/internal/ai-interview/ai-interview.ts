import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { InterviewService, AnswerItem } from '../../services/interview.service';

type InterviewState = 'idle' | 'creating_session' | 'ready' | 'submitting_answers' | 'generating_report' | 'completed' | 'error';

@Component({
  selector: 'app-ai-interview',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './ai-interview.html',
  styleUrl: './ai-interview.css',
})
export class AiInterview implements OnInit {
  interviewService = inject(InterviewService);
  router = inject(Router);

  state: InterviewState = 'idle';
  errorMessage = '';

  targetJobTitle = '';
  targetCompanyName = '';
  sessionId = '';
  consentGiven = false;

  questions: string[] = [
    "Tell us about yourself and why you are interested in this role.",
    "What relevant technical skills or projects make you suitable for this role?",
    "Describe a challenging problem you solved in a project.",
    "How do you handle deadlines or unexpected issues?",
    "How do you communicate and collaborate in a team?",
    "What skills do you still need to improve for this role?"
  ];

  answers: string[] = new Array(6).fill('');

  ngOnInit() {
    // idle state
  }

  async startSession() {
    if (!this.targetJobTitle.trim()) {
      this.errorMessage = 'Target Job Title is required to start the interview.';
      return;
    }
    
    this.state = 'creating_session';
    this.errorMessage = '';
    try {
      const res = await this.interviewService.createInterviewSession(this.targetJobTitle, undefined, this.targetCompanyName);
      this.sessionId = res.session_id;
      this.state = 'ready';
    } catch (e: any) {
      this.errorMessage = 'Failed to create session: ' + (e.error?.detail || e.message);
      this.state = 'error';
    }
  }

  get isSubmitValid(): boolean {
    if (!this.consentGiven) return false;
    for (const ans of this.answers) {
      if (!ans || ans.trim().length < 20) {
        return false;
      }
    }
    return true;
  }

  async submitAndGenerate() {
    if (!this.isSubmitValid) return;

    this.state = 'submitting_answers';
    this.errorMessage = '';

    const formattedAnswers: AnswerItem[] = this.questions.map((q, i) => ({
      question: q,
      answer_text: this.answers[i],
      answer_order: i + 1
    }));

    try {
      await this.interviewService.submitAnswers(this.sessionId, this.consentGiven, formattedAnswers);
      
      this.state = 'generating_report';
      const genRes = await this.interviewService.generateReport(this.sessionId);
      
      this.state = 'completed';
      this.router.navigate(['/internal/employer-report', genRes.report_id]);
    } catch (e: any) {
      this.errorMessage = 'An error occurred during submission/generation: ' + (e.error?.detail || e.message);
      this.state = 'error';
    }
  }
}
