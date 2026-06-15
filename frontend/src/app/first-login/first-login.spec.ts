import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FirstLogin } from './first-login';

describe('FirstLogin', () => {
  let component: FirstLogin;
  let fixture: ComponentFixture<FirstLogin>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FirstLogin],
      providers: [provideRouter([{path: 'auth', component: FirstLogin}, {path: 'internal/dashboard', component: FirstLogin}])],
    }).compileComponents();

    fixture = TestBed.createComponent(FirstLogin);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
