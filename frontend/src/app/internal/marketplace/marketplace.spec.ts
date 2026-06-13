import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Marketplace } from './marketplace';
import { Internal } from '../internal';
import { AuthService } from '../../services/auth-service';

describe('Marketplace', () => {
  let component: Marketplace;
  let fixture: ComponentFixture<Marketplace>;

  const mockInternal = {
    toggleSidebar: () => {},
    closeSidebar: () => {},
    isSidebarOpen: false
  };

  const mockAuthService = {
    getUser: () => Promise.resolve({ user_metadata: { full_name: 'Test User' }, email: 'test@example.com' }),
    supabaseClient: {
      from: () => ({
        select: () => ({
          eq: () => ({
            order: () => Promise.resolve({ data: [], error: null })
          })
        })
      })
    }
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Marketplace],
      providers: [
        { provide: Internal, useValue: mockInternal },
        { provide: AuthService, useValue: mockAuthService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(Marketplace);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

