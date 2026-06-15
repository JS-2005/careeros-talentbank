import { Internal } from '../internal';
import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AiInterview } from './ai-interview';

describe('AiInterview', () => {
  let component: AiInterview;
  let fixture: ComponentFixture<AiInterview>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiInterview],
      providers: [provideRouter([]), { provide: Internal, useValue: { toggleSidebar: () => {} } }],
    }).compileComponents();

    fixture = TestBed.createComponent(AiInterview);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
