import { Routes } from '@angular/router';
import { LandingPage } from './landing-page/landing-page';
import { Auth } from './auth/auth';
import { Internal } from './internal/internal';
import { Marketplace } from './internal/marketplace/marketplace';
import { AiInterview } from './internal/ai-interview/ai-interview';
import { AiInterviewLive } from './internal/ai-interview-live/ai-interview-live';
import { Profile } from './internal/profile/profile';
import { EmployerReports } from './internal/employer-reports/employer-reports';
import { EmployerReport } from './internal/employer-report/employer-report';
import { JobMatching } from './internal/job-matching/job-matching';
import { FirstLogin } from './first-login/first-login';
import { MeetingLobby } from './meeting-lobby/meeting-lobby';
import { MeetingRoom } from './meeting-room/meeting-room';
import { MeetingReport } from './meeting-report/meeting-report';
import { authGuard } from './guards/auth-guard';

import { EmployerReportDemo } from './employer-report-demo/employer-report-demo';

export const routes: Routes = [
    { path: '', component: LandingPage },
    { path: 'auth', component: Auth },
    { path: 'employer-report-demo', component: EmployerReportDemo },
    { path: 'first-login', component: FirstLogin, canActivate: [authGuard] },
    { path: ':id/meeting-lobby', component: MeetingLobby, canActivate: [authGuard] },
    { path: ':id/meeting-room', component: MeetingRoom, canActivate: [authGuard] },
    { path: ':id/meeting-report', component: MeetingReport, canActivate: [authGuard] },
    {
        path: 'internal',
        component: Internal,
        children: [
            { path: 'marketplace', component: Marketplace },
            { path: 'ai-interview', component: AiInterview },
            { path: 'ai-interview-live', component: AiInterviewLive },
            { path: 'employer-reports', component: EmployerReports },
            { path: 'employer-report/:reportId', component: EmployerReport },
            { path: 'profile', component: Profile }, 
            { path: 'job-matching', component: JobMatching }, 
            { path: '', redirectTo:'marketplace', pathMatch:'full'}
        ], 
        canActivate: [authGuard]
    }
];
