// SPDX-License-Identifier: MIT

package main

import (
	"strconv"
	"testing"
	"testing/synctest"
)

// OnAlarm calls notify for every alarm, and nothing reads the channel with
// the default --wait-alarms 0: more alarms than its buffer holds must still
// return at once.
func TestNotifyReturnsWithAFullBufferAndNoReader(t *testing.T) {
	for _, calls := range []int{0, 1, 63, 64, 65, 100} {
		t.Run(strconv.Itoa(calls), func(t *testing.T) {
			synctest.Test(t, func(t *testing.T) {
				ch := make(chan struct{}, 64)
				done := make(chan struct{})
				go func() {
					defer close(done)
					for range calls {
						notify(ch)
					}
				}()
				synctest.Wait()
				select {
				case <-done:
				default:
					t.Errorf("%d calls: notify blocked with %d wakeups pending", calls, len(ch))
					for { // let the caller finish, so that the bubble can end
						select {
						case <-ch:
						case <-done:
							return
						}
					}
				}
				if want := min(calls, cap(ch)); len(ch) != want {
					t.Errorf("%d calls: %d wakeups pending, want %d", calls, len(ch), want)
				}
			})
		})
	}
}
