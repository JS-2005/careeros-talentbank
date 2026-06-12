import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MeetingRoom } from './meeting-room';

describe('MeetingRoom', () => {
  let component: MeetingRoom;
  let fixture: ComponentFixture<MeetingRoom>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeetingRoom],
    }).compileComponents();

    fixture = TestBed.createComponent(MeetingRoom);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
