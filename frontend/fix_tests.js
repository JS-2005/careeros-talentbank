const fs = require('fs');

const testFiles = [
  'src/app/first-login/first-login.spec.ts',
  'src/app/landing-page/landing-page.spec.ts',
  'src/app/meeting-report/meeting-report.spec.ts',
  'src/app/meeting-lobby/meeting-lobby.spec.ts',
  'src/app/internal/internal.spec.ts',
  'src/app/internal/ai-interview/ai-interview.spec.ts',
  'src/app/internal/job-matching/job-matching.spec.ts',
  'src/app/internal/profile/profile.spec.ts'
];

testFiles.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');

  if (!content.includes('provideRouter')) {
    content = "import { provideRouter } from '@angular/router';\n" + content;
  }

  let providers = `providers: [provideRouter([])`;

  if (file.includes('internal/') && !file.includes('internal.spec.ts')) {
    if (!content.includes('import { Internal }')) {
      content = `import { Internal } from '../internal';\n` + content;
    }
    providers += `, { provide: Internal, useValue: { toggleSidebar: () => {} } }`;
  }
  
  providers += `]`;

  if (content.includes('imports: [')) {
    content = content.replace(/imports: \[([^\]]+)\]/, (match, group1) => `imports: [${group1}],\n      ${providers}`);
  }

  fs.writeFileSync(file, content);
  console.log('Fixed', file);
});
