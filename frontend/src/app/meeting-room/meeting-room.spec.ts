import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { MeetingRoom } from './meeting-room';
import { AuthService } from '../services/auth-service';

describe('MeetingRoom', () => {
  let component: MeetingRoom;
  let fixture: ComponentFixture<MeetingRoom>;

  const mockActivatedRoute = {
    snapshot: {
      paramMap: {
        get: (key: string) => '123'
      }
    }
  };

  const mockRouter = {
    navigate: (commands: any[]) => {}
  };

  const mockAuthService = {
    getUser: () => Promise.resolve({ user_metadata: { full_name: 'Test User' }, email: 'test@example.com' }),
    supabaseClient: {
      from: () => ({
        select: () => ({
          eq: () => ({
            single: () => Promise.resolve({ data: null, error: null })
          })
        })
      })
    }
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeetingRoom],
      providers: [
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: Router, useValue: mockRouter },
        { provide: AuthService, useValue: mockAuthService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(MeetingRoom);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
