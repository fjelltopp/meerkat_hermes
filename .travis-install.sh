if [ "$TRAVIS_BUILD" = "docs" ]
then
    pip install .

elif [ "$TRAVIS_BUILD" = "tests" ]
then
    pip install .
    git clone --branch development --single-branch https://github.com/meerkat-code/meerkat_libs.git ../meerkat_libs
    pip install ../meerkat_libs
fi
