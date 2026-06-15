import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MeetingLobby } from './meeting-lobby';

describe('MeetingLobby', () => {
  let component: MeetingLobby;
  let fixture: ComponentFixture<MeetingLobby>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeetingLobby],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(MeetingLobby);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
