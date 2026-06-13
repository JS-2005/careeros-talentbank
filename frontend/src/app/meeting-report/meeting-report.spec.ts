import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MeetingReport } from './meeting-report';

describe('MeetingReport', () => {
  let component: MeetingReport;
  let fixture: ComponentFixture<MeetingReport>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeetingReport],
    }).compileComponents();

    fixture = TestBed.createComponent(MeetingReport);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
