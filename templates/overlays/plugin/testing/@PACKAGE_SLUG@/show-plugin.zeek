# @TEST-EXEC: zeek -NN @PACKAGE_NAMESPACE@::@PACKAGE_NAME@ |sed -e 's/version.*)/version)/g' >output
# @TEST-EXEC: btest-diff output
