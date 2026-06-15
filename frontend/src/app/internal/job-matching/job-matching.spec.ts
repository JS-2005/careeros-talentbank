import { Internal } from '../internal';
import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobMatching } from './job-matching';

describe('JobMatching', () => {
  let component: JobMatching;
  let fixture: ComponentFixture<JobMatching>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobMatching],
      providers: [provideRouter([]), { provide: Internal, useValue: { toggleSidebar: () => {} } }],
    }).compileComponents();

    fixture = TestBed.createComponent(JobMatching);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
